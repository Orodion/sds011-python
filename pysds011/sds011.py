#!/usr/bin/env python3

""" Class for control the SDS011 sensor. """

from typing import List, Optional
from .definitions import WorkingMode
from .definitions import ReportMode
from .definitions import Modifier
from .definitions import Frame
from .definitions import Command
from .definitions import MessageType

REPLY_LENGTH = 10
# The sensor sends one 10 byte frame per second, so a header must show up
# within a few frames unless the line is broken.
MAX_HEADER_SEARCH_BYTES = 5 * REPLY_LENGTH
MAX_REPLY_POLLS = 10


class SDS011:
    """ Class for control the SDS011 sensor. """
    def __init__(self, serial):
        """ Initialisation """
        self.device_id = [255, 255]
        self.firmware = None
        self.serial = serial
        self.serial.flushInput()
        self.device_id = None
        self.data = {'PM2.5': 0.0, 'PM10': 0.0}
        self.last_command = b''
        self.last_reply = b''
        self.get_firmware_version()

    def read_message(self):
        """ Read message from serial interface

        Raises TimeoutError if the serial read times out or no frame header
        is found within MAX_HEADER_SEARCH_BYTES bytes.
        """
        header = bytes([Frame.HEADER.value])
        for _ in range(MAX_HEADER_SEARCH_BYTES):
            byte = bytes(self.serial.read(size=1))
            if not byte:
                raise TimeoutError('No data received from sensor!')
            if byte == header:
                break
        else:
            raise TimeoutError('No frame header received from sensor!')
        body = bytes(self.serial.read(size=REPLY_LENGTH - 1))
        if len(body) != REPLY_LENGTH - 1:
            raise TimeoutError('Incomplete frame received from sensor!')
        self.last_reply = header + body

    def command_message_valid(self) -> bool:
        """ Validate generated command """
        if len(self.last_command) == 19:
            if (self.last_command[0] == Frame.HEADER.value and
                    self.last_command[1] == MessageType.COMMAND.value and
                    self.last_command[-1] == Frame.TAIL.value):
                if self.__valid_checksum(self.last_command):
                    return True
        return False

    def reply_message_valid(self) -> bool:
        """ Validate reply from device """
        if len(self.last_reply) == 10:
            if (self.last_reply[0] == Frame.HEADER.value and
                    self.last_reply[-1] == Frame.TAIL.value):
                if (self.last_reply[1] == MessageType.COMMAND_REPLY.value or
                        self.last_reply[1] == MessageType.DATA.value):
                    if self.__valid_checksum(self.last_reply):
                        return True
        return False

    @staticmethod
    def calculate_checksum(message_data: List[int]) -> int:
        """ Calculate checksum """
        return sum(message_data) % 256

    def __valid_checksum(self, message) -> bool:
        """ Validaty correct checksum for command or reply """
        message_data = []
        for i in range(len(message[2:-2])):
            message_data.append(message[2+i])
        return SDS011.calculate_checksum(message_data) == message[-2]

    def decode_data(self) -> None:
        """ Decode measured data from device if reply from device is valid """
        if (self.reply_message_valid() and
                self.last_reply[1] == MessageType.DATA.value):
            self.data['PM2.5'] = ((self.last_reply[3] << 8) + self.last_reply[2])/10
            self.data['PM10'] = ((self.last_reply[5] << 8) + self.last_reply[4])/10

    def read_and_decode_data(self):
        """ Read and decode data from device """
        self.read_message()
        self.decode_data()

    def print_firmware(self):
        """ Print firmware version """
        firmware = 'Firmware (YY-MM-DD): '
        firmware += str(self.firmware['year']) + '-'
        firmware += str(self.firmware['month']) + '-'
        firmware += str(self.firmware['day'])
        print(firmware)

    def print_data(self):
        """ Print measured data """
        print('Measured PM2.5 value is: ' + str(self.data['PM2.5']) + ' ug/m^3')
        print('Measured PM10  value is: ' + str(self.data['PM10']) + ' ug/m^3')

    def __decode_device_id(self):
        """ Decode device id from reply message """
        if self.reply_message_valid():
            self.device_id = [self.last_reply[6], self.last_reply[7]]

    def get_device_id(self) -> str:
        """ Return device id as hex string """
        return str(bytes(self.device_id).hex()).upper()

    def __prepare_command(self, command: Command, data: List[int],
                          device_id: Optional[List[int]] = None) -> None:
        """ Build command for device control """
        assert len(data) <= 12
        if not device_id:
            device_id = [255, 255]
        data += [0, ]*(12-len(data)) + device_id
        command_message = [Frame.HEADER.value, MessageType.COMMAND.value, command.value]
        command_message += data
        command_message.append(SDS011.calculate_checksum([command.value] + data))
        command_message.append(Frame.TAIL.value)
        self.last_command = bytes(command_message)
        if not self.command_message_valid():
            self.last_command = None

    def __polling_for_reply(self) -> None:
        """ Read messages from device until reply for the last command is received """
        for _ in range(MAX_REPLY_POLLS):
            self.read_message()
            if self.__is_reply_to_last_command():
                break
        else:
            raise TimeoutError('No reply received from sensor!')

    def __is_reply_to_last_command(self) -> bool:
        """ Check that the last reply is valid and answers the last command """
        if not self.reply_message_valid():
            return False
        command_id = self.last_command[2]
        if command_id == Command.QUERY_DATA.value:
            return self.last_reply[1] == MessageType.DATA.value
        return (self.last_reply[1] == MessageType.COMMAND_REPLY.value and
                self.last_reply[2] == command_id)

    def __write_and_wait_reply(self) -> None:
        """ Send command to device and wait for reply """
        if self.last_command:
            self.serial.write(self.last_command)
            self.__polling_for_reply()

    def set_report_mode(self, report_mode: ReportMode,
                        device_id: Optional[List[int]] = None) -> None:
        """ Set report mode """
        self.__prepare_command(command=Command.REPORT_MODE,
                               data=[Modifier.SET.value, report_mode.value],
                               device_id=device_id)
        self.__write_and_wait_reply()

    def get_report_mode(self, device_id: Optional[List[int]] = None):
        """ Get report mode """
        self.__prepare_command(command=Command.REPORT_MODE,
                               data=[Modifier.GET.value],
                               device_id=device_id)
        self.__write_and_wait_reply()

    def query_data(self, device_id: Optional[List[int]] = None):
        """ Query data from device """
        self.__prepare_command(command=Command.QUERY_DATA,
                               data=[0],
                               device_id=device_id)
        self.__write_and_wait_reply()

    def set_device_id(self, new_device_id: List[int],
                      device_id: Optional[List[int]] = None) -> None:
        """ Set device id """
        data = [0]*10 + new_device_id
        self.__prepare_command(command=Command.SET_DEVICE_ID,
                               data=data,
                               device_id=device_id)
        self.__write_and_wait_reply()
        self.__decode_device_id()

    def set_working_mode(self, working_mode: WorkingMode,
                         device_id: Optional[List[int]] = None) -> None:
        """ Set working mode """
        self.__prepare_command(command=Command.WORKING_MODE,
                               data=[Modifier.SET.value, working_mode.value],
                               device_id=device_id)
        self.__write_and_wait_reply()

    def get_working_mode(self, device_id: Optional[List[int]] = None) -> None:
        """ Get working mode """
        self.__prepare_command(command=Command.WORKING_MODE,
                               data=[Modifier.GET.value],
                               device_id=device_id)
        self.__write_and_wait_reply()

    def get_firmware_version(self, device_id: Optional[List[int]] = None) -> None:
        """ Get firmware version and decode firmware and device id"""
        self.__prepare_command(command=Command.GET_FIRMWARE,
                               data=[0],
                               device_id=device_id)
        self.__write_and_wait_reply()
        self.firmware = {'year': self.last_reply[3],
                         'month': self.last_reply[4],
                         'day': self.last_reply[5]}
        self.__decode_device_id()

    def set_working_period(self, working_period: int = 0,
                           device_id: Optional[List[int]] = None) -> None:
        """ Set working period """
        # valid values 1 min to 30 min and 0 for continuous
        # work 30 seconds and sleep n*60-30 seconds】
        assert 0 <= working_period <= 30
        self.__prepare_command(command=Command.WORKING_PERIOD,
                               data=[Modifier.SET.value, working_period],
                               device_id=device_id)
        self.__write_and_wait_reply()

    def get_working_period(self, device_id: Optional[List[int]] = None) -> None:
        """ Get working mode """
        self.__prepare_command(command=Command.WORKING_PERIOD,
                               data=[Modifier.GET.value],
                               device_id=device_id)
        self.__write_and_wait_reply()
