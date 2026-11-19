#!/usr/bin/env python3

""" Regression tests for reply handling of the SDS011 protocol """

import unittest
from typing import List

from pysds011.sds011 import SDS011
from pysds011.definitions import Frame, MessageType
from pysds011.simulation.sim_sds011 import SimulationSDS011


def build_frame(message_type: MessageType, payload: List[int]) -> bytes:
    """ Build a 10 byte frame as sent by the sensor """
    return bytes([Frame.HEADER.value, message_type.value] + payload
                 + [sum(payload) % 256, Frame.TAIL.value])


class ActiveModeSimulation(SimulationSDS011):
    """ Simulation that sends a data frame before every command reply """

    def __init__(self, data_payload: List[int]):
        super().__init__()
        self.data_payload = data_payload

    def write(self, data) -> int:
        """ Queue a data frame in front of the reply """
        written = super().write(data)
        self.data = build_frame(MessageType.DATA, self.data_payload) + self.data
        self.offset = 0
        return written


class SilentSerial(SimulationSDS011):
    """ Serial port whose read timeout always expires """

    def read(self, size: int = 1) -> bytes:
        """ Return nothing like an expired read timeout """
        return b''


class TruncatedSerial(SimulationSDS011):
    """ Serial port that delivers a header byte and then times out """

    def __init__(self):
        super().__init__()
        self.header_sent = False

    def read(self, size: int = 1) -> bytes:
        """ Return one header byte, then nothing """
        if self.header_sent:
            return b''
        self.header_sent = True
        return bytes([Frame.HEADER.value])


class NoiseSerial(SimulationSDS011):
    """ Serial port that only delivers bytes without a frame header """

    def read(self, size: int = 1) -> bytes:
        return b'\x00' * size


class TestReplyHandling(unittest.TestCase):
    """ Replies must be matched by type, command id and checksum """

    def test_data_frame_with_command_id_as_pm25_byte_is_not_taken_as_reply(self):
        """ Data frame with command id as pm25 byte is not taken as reply """
        # PM2.5 low byte 7 equals the GET_FIRMWARE command id
        simulation = ActiveModeSimulation(data_payload=[7, 1, 40, 0, 10, 11])
        sensor = SDS011(simulation)
        expected = dict(zip(['year', 'month', 'day'], simulation.firmware))
        self.assertEqual(sensor.firmware, expected)
        self.assertEqual(sensor.last_reply[1], MessageType.COMMAND_REPLY.value)

    def test_query_data_still_accepts_data_frame(self):
        """ Query data still accepts data frame """
        simulation = ActiveModeSimulation(data_payload=[50, 0, 60, 0, 10, 11])
        sensor = SDS011(simulation)
        sensor.query_data()
        sensor.decode_data()
        self.assertEqual(sensor.data, {'PM2.5': 5.0, 'PM10': 6.0})

    def test_decode_data_ignores_command_reply(self):
        """ Decode data ignores command reply """
        sensor = SDS011(SimulationSDS011())
        self.assertEqual(sensor.last_reply[1], MessageType.COMMAND_REPLY.value)
        sensor.decode_data()
        self.assertEqual(sensor.data, {'PM2.5': 0.0, 'PM10': 0.0})

    def test_decode_data_decodes_data_frame(self):
        """ Decode data decodes data frame """
        sensor = SDS011(SimulationSDS011())
        sensor.last_reply = build_frame(MessageType.DATA, [34, 1, 40, 2, 10, 11])
        sensor.decode_data()
        self.assertEqual(sensor.data, {'PM2.5': 29.0, 'PM10': 55.2})


class TestReadTimeouts(unittest.TestCase):
    """ Short or missing reads must raise TimeoutError """

    def test_no_data_raises_timeout(self):
        """ No data raises timeout """
        with self.assertRaises(TimeoutError):
            SDS011(SilentSerial())

    def test_truncated_frame_raises_timeout(self):
        """ Truncated frame raises timeout """
        with self.assertRaises(TimeoutError):
            SDS011(TruncatedSerial())

    def test_endless_noise_without_header_raises_timeout(self):
        """ Endless noise without header raises timeout """
        with self.assertRaises(TimeoutError):
            SDS011(NoiseSerial())


if __name__ == '__main__':
    unittest.main()
