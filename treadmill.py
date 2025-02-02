import asyncio
import bleak
import struct
import time
import threading
from bleak import BleakClient
from i3pystatus import IntervalModule, formatp
from i3pystatus.core.color import ColorRangeModule


class TreadmillDataClient(object):
    def __init__(self, client, treadmill_data_characteristic):
        self.treadmill_data_characteristic = treadmill_data_characteristic
        self.client = client
        self.data = {}
         
    async def read(self):
        await self.client.start_notify(self.treadmill_data_characteristic, lambda sender, data: self.treadmill_data_handler(sender, data))
        await asyncio.sleep(2)
        await self.client.stop_notify(self.treadmill_data_characteristic)
        return self.data

    def treadmill_data_handler(self, sender, data):
        parsed_data = self.parse_treadmill_data(data)
        self.data = parsed_data 

    def parse_uint8(self, byte_array):
        return struct.unpack('B', bytes(byte_array[:1]))[0], byte_array[1:]

    def parse_uint16(self, byte_array):
        return struct.unpack('H', bytes(byte_array[:2]))[0], byte_array[2:]

    def parse_sint16(self, byte_array):
        return struct.unpack('h', bytes(byte_array[:2]))[0], byte_array[2:]

    def parse_treadmill_data(self, byte_array):
        # Ensure we have at least two bytes for the flags
        if len(byte_array) < 2:
            raise ValueError("Input byte array is too short to contain valid flags")

        # Extract the two flag bytes
        flags_byte1 = byte_array[0]
        flags_byte2 = byte_array[1]
        byte_array = byte_array[2:]
        
        # Create a dictionary to store the parsed data
        data = {}

        # Mandatory fields        
        speed, byte_array = self.parse_uint16(byte_array)
        data['instantaneous_speed'] = speed

        # Check flags and parse data accordingly (byte 1)

        # Average Speed (bit 1)
        if flags_byte1 & 0x02:
            speed, byte_array = self.parse_uint16(byte_array)
            data['average_speed'] = speed
        
        # Total Distance (bit 2)
        if flags_byte1 & 0x04:
            distance_bytes = byte_array[:3] + bytearray([0x00]) # Add 4th byte because the distance is 24 bit
            distance = struct.unpack('I', bytes(distance_bytes))[0]
            byte_array = byte_array[3:]
            data['total_distance'] = distance
        
        # Inclination and Ramp Angle Setting (bit 3)
        if flags_byte1 & 0x08:
            incline, byte_array = self.parse_sint16(byte_array)
            ramp_angle, byte_array = self.parse_sint16(byte_array)
            data['inclination'] = incline
            data['ramp_angle'] = ramp_angle
        
        # Elevation Gain (bit 4)
        if flags_byte1 & 0x10:
            elevation_gain, byte_array= self.parse_uint16(byte_array)
            negative_elevation_gain, byte_array = self.parse_uint16(byte_array)
            data['elevation_gain'] = elevation_gain
            data['negative_elevation_gain'] = negative_elevation_gain

        # Instantaneous Pace (bit 5)
        if flags_byte1 & 0x20:
            pace, byte_array = self.parse_uint8(byte_array)
            data['instantaneous_pace'] = pace

        # Average Pace (bit 6)
        if flags_byte1 & 0x40:
            avg_pace, byte_array = self.parse_uint8(byte_array)
            data['average_pace'] = avg_pace
        
        # Expended Energy (bit 7)
        if flags_byte1 & 0x80:
            total_energy, byte_array = self.parse_uint16(byte_array)
            energy_per_hour, byte_array = self.parse_uint16(byte_array)
            energy_per_minute, byte_array = self.parse_uint8(byte_array)
            data['expended_energy'] = total_energy
            data['energy_per_hour'] = energy_per_hour
            data['energy_per_minute'] = energy_per_minute

        # Check flags and parse data accordingly (byte 2)
        # Heart Rate (bit 0)
        if flags_byte2 & 0x01:
            heart_rate, byte_array = self.parse_uint8(byte_array)
            data['heart_rate'] = heart_rate

        # Metabolic Equivalent (bit 1)
        if flags_byte2 & 0x02:
            met_eq, byte_array= self.parse_uint8(byte_array)
            data['metabolic_equivalent'] = met_eq
        
        # Elapsed Time (bit 2)
        if flags_byte2 & 0x04:
            elapsed_time, byte_array = self.parse_uint16(byte_array) 
            data['elapsed_time'] = elapsed_time
        
        # Remaining Time (bit 3)
        if flags_byte2 & 0x08:
            remaining_time, byte_array = self.parse_uint16(byte_array)
            data['remaining_time'] = remaining_time
        
        # Force on Belt and Power Output (bit 4)
        if flags_byte2 & 0x10:
            force,byte_array = self.parse_sint16(byte_array)
            power_output,byte_array = self.parse_sint16(byte_array)
            data['force_on_belt'] = force
            data['power_output'] = power_output

        return data

class FitnessMachineControlPoint(object):
    def __init__(self, client, machine_control_point_characteristic):
        self.machine_control_point_characteristic = machine_control_point_characteristic
        self.client = client
            
    async def send_resume_command(self):
        await self.client.write_gatt_char(self.machine_control_point_characteristic, bytearray([0x07]), response=False)

    async def send_pause_command(self):
        await self.client.write_gatt_char(self.machine_control_point_characteristic, bytearray([0x08, 0x02]), response=False)

    async def send_stop_command(self):
        await self.client.write_gatt_char(self.machine_control_point_characteristic, bytearray([0x08, 0x01]), response=False)

    async def set_speed(self, speed):
        speed_bytes = speed.to_bytes(2, byteorder='little')
        await self.client.write_gatt_char(self.machine_control_point_characteristic, bytearray([0x02, speed_bytes[0], speed_bytes[1]]), response=False)

class TreadmillController(object):
    control_point = None
    treadmill_data_client = None
    logger = None 
    client = None

    def __init__(self, logger):
        self.logger = logger 

    async def connect(self):
        DEVICE_NAME = "EsangLinker"
        scanner = bleak.BleakScanner()
        devices = await scanner.discover()
        walking_pad = None
        for device in devices:
            if(device.name == DEVICE_NAME):
                walking_pad = device
                self.logger.debug("Found walking pad: " + walking_pad.address + " " + walking_pad.name)
                break
        if(walking_pad is None):
            self.logger.error("Walking pad not found")
            return None
        self.client = BleakClient(walking_pad.address)
        await self.client.connect()
        self.logger.info("Connected to " + walking_pad.address)
        try: 
            characteristics = await self.get_all_characteristics()
            control_point_characteristic = self.get_fitness_machine_control_point_characteristic(characteristics)
            treadmill_data_characteristic = self.get_treadmill_data_characteristic(characteristics)
            self.control_point = FitnessMachineControlPoint(self.client, control_point_characteristic)
            self.treadmill_data_client = TreadmillDataClient(self.client, treadmill_data_characteristic)

        except Exception as e:
            self.logger.exception("Failed to connect.")
            await self.client.disconnect()
            return


    async def get_all_characteristics(self):
        if(self.client is None):
            self.logger.error("Client not connected")
            return []   
        characteristics = []
        for service in self.client.services:
            for char in service.characteristics:
                characteristics.append(char)
        return characteristics

    def get_fitness_machine_control_point_characteristic(self, characteristics):
        for char in characteristics:
            if not char:
                continue    
            if char.uuid[:8] == "00002ad9":
                return char
        self.logger.error("Fitness Machine Control Point characteristic not found")
        return None
        
    def get_treadmill_data_characteristic(self, characteristics):
        for char in characteristics:
            if not char:
                continue    
            if char.uuid[:8] == "00002acd":
                return char
        self.logger.error("Treadmill Data characteristic not found")
        return None
 
class Treadmill(IntervalModule, ColorRangeModule):
    settings = (
        ("format", "format string"),
    )
    format = "{instantaneous_speed}km/h {total_distance}m"
    controller = None
    data = {}
    output = {}
    event_loop = None
    interval = 1
    on_leftclick = "pause_resume"
    on_rightclick = "close"
    on_upscroll = "increment_speed"
    on_downscroll = "decrement_speed"
    pause_disconnect_timeout = 300
    pause_start = None
    is_inactive = False
    task_queue = []
    thread = None

    def update_thread(self):
        self.logger.info("Starting update thread")
        while True:
            self.logger.debug("Entering run " + str(self.pause_start))
            if not self.is_inactive and (self.controller.client is None or not self.controller.client.is_connected):
                self.pause_start = None
                self.event_loop.run_until_complete(self.controller.connect())

            if self.controller.client is None or not self.controller.client.is_connected:
                format_str = "Treadmill not connected."
                self.data = {}
            else:
                try:
                    while len(self.task_queue) > 0:
                        task = self.task_queue.pop(0)
                        self.logger.info("Executing scheduled task.")
                        self.event_loop.run_until_complete(task)
                    self.data = self.event_loop.run_until_complete(self.controller.treadmill_data_client.read())
                    if self.data["instantaneous_speed"] == 0:
                        if self.pause_start is None:
                            self.pause_start = time.time()
                            self.logger.info("Starting paused timeout.")
                        elif time.time() - self.pause_start > self.pause_disconnect_timeout:
                            self.event_loop.run_until_complete(self.controller.client.disconnect())
                            self.is_inactive = True
                            self.logger.info("Disconnected from treadmill due to inactivity.")
                    else:
                        self.pause_start = None

                    format_str = self.format

                    data = self.data.copy()
                    # Convert speed to km/h
                    data["instantaneous_speed"] = data["instantaneous_speed"] / 100
                    self.output = {
                        "full_text": formatp(format_str, **data).strip(),
                        'color': "E7BA3C"
                    }
                except Exception as e:
                    self.logger.error("Error in update_thread" + str(e))
                    self.data = {}
                    format_str = "Error reading treadmill data."
                    self.output = {
                        "full_text": format_str,
                        'color': "FF0000"
                    }
                    break
            time.sleep(self.interval)
        self.controller.treadmill.close()
        self.logger.debug("Exiting run")


    def init(self):
        self.event_loop = asyncio.new_event_loop()
        self.controller = TreadmillController(self.logger)
        self.thread = threading.Thread(target=self.update_thread, daemon=True)
        self.thread.start()

    def run(self):
        pass
    
    def pause_resume(self):
        self.logger.info("Pause/Resume")
        if self.is_inactive:
            self.logger.info("Reconnecting")
            self.is_inactive = False
            self.task_queue.append(self.event_loop.create_task(self.controller.control_point.send_resume_command()))
            return

        if "instantaneous_speed" not in self.data:
            self.logger.info("Failed to resume.")
            return

        if self.data["instantaneous_speed"] == 0:
            self.task_queue.append(self.event_loop.create_task(self.controller.control_point.send_resume_command()))
            self.logger.info("Created resume task")
        else: 
            self.task_queue.append(self.event_loop.create_task(self.controller.control_point.send_pause_command()))
            self.logger.info("Created pause task")
        self.logger.info("Returning from pause_resume")

    def increment_speed(self):
        if "instantaneous_speed" not in self.data:
            self.logger.info("Failed to increment speed.")
            return
        new_speed = self.data["instantaneous_speed"] + 10
        self.task_queue.append(self.event_loop.create_task(self.controller.control_point.set_speed(new_speed)))
        self.data["instantaneous_speed"] = new_speed

    def decrement_speed(self):
        if "instantaneous_speed" not in self.data:
            self.logger.info("Failed to decrement speed.")
            return
        new_speed = self.data["instantaneous_speed"] - 10
        self.event_loop.create_task(self.controller.control_point.set_speed(new_speed))
        self.data["instantaneous_speed"] = new_speed

    def close(self):
        self.event_loop.create_task(self.controller.client.disconnect())
