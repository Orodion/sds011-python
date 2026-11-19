#!/usr/bin/env python3

""" Simulation for serial connection with connected SDS011 sensor """

from pathlib import Path
from typing import List
from ..definitions import WorkingMode, ReportMode, Modifier, Frame, Command, MessageType
from ..sds011 import SDS011


class SimulationSDS011:
    """ Simulation class for SDS011 """

    def __init__(self):
        self.working_mode = WorkingMode.WORK_MODE
        self.report_mode = ReportMode.REPORT_ACTIVE_MODE
        self.working_period = 0
        self.device_id = [10, 11]
        self.firmware = [15, 7, 10]

        # [ PM2.5_low_byte, PM2.5_high_byte, PM10_low_byte, PM10_high_byte]
        self.measurement_data = [34, 0, 40, 0]

        self.path_to_sample_binary = (Path(__file__).resolve().parents[2]
                                      / 'data/sample_data_sds011.hex')
        self.data = bytearray()
        self.offset = 0

        self.command = None
        self.reply = None

    def read(self, size: int = 1) -> bytes:
        """ Returns bytes from self.data bytes buffer """
        read_buffer = bytearray()
        for _ in range(size):
            # reset offset on last data element
            if self.offset >= len(self.data):
                self.offset = 0
            read_buffer.append(self.data[self.offset])
            self.offset += 1
        return bytes(read_buffer)

    def flushInput(self) -> None:
        """ Dummy for function in serial.Serial().flushInput() """

    def close(self) -> None:
        """ Dummy for function in serial.Serial().close() """

    def read_sample_data_sds011(self) -> None:
        """ Load sample data from file """
        file = open(self.path_to_sample_binary, 'rb')
        data = file.read()
        file.close()
        self.data = data

    def command_message_valid(self) -> bool:
        """ Validate received command """
        if len(self.command) == 19:
            if (self.command[0] == Frame.HEADER.value and
                    self.command[1] == MessageType.COMMAND.value and
                    self.command[-1] == Frame.TAIL.value):
                message_data = []
                for i in range(len(self.command[2:-2])):
                    message_data.append(self.command[2+i])
                if SDS011.calculate_checksum(message_data) == self.command[-2]:
                    if (self.command[-4:-2] == bytes([255, 255]) or
                            self.command[-4:-2] == bytes(self.device_id)):
                        return True
        return False

    def apply_command(self) -> List[int]:
        """ Apply a settings command and return its reply payload bytes """
        command_id, modifier, value = self.command[2], self.command[3], self.command[4]
        is_set = modifier == Modifier.SET.value

        if command_id == Command.WORKING_MODE.value:
            if is_set:
                self.working_mode = WorkingMode(value)
            return [modifier, self.working_mode.value]

        if command_id == Command.REPORT_MODE.value:
            if is_set:
                self.report_mode = ReportMode(value)
            return [modifier, self.report_mode.value]

        if command_id == Command.WORKING_PERIOD.value:
            if is_set:
                self.working_period = value
                assert 0 <= self.working_period <= 30
            return [modifier, self.working_period]

        if command_id == Command.SET_DEVICE_ID.value:
            self.device_id = [self.command[13], self.command[14]]
            return [0, 0]

        return []

    def build_reply(self) -> None:
        """ Build reply for received command """
        if self.command_message_valid():
            data = [self.command[2]] + self.apply_command()
            command_type = MessageType.COMMAND_REPLY

            data.append(0)

            if self.command[2] == Command.GET_FIRMWARE.value:
                data = data[:-1] + self.firmware

            if self.command[2] == Command.QUERY_DATA.value:
                command_type = MessageType.DATA
                data = data[:-2] + self.measurement_data

            data += self.device_id

            reply = [Frame.HEADER.value, command_type.value]
            reply += data
            reply.append(SDS011.calculate_checksum(data))
            reply.append(Frame.TAIL.value)

            self.reply = bytes(reply)
            self.data = self.reply
        else:
            self.reply = None

    def write(self, data) -> int:
        """ Receive and process commands like serial.Serial().write()"""
        self.command = data
        self.build_reply()
        return len(data)
