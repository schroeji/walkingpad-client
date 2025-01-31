import asyncio
import bleak
import time
import struct
from bleak import BleakClient

class TreadmillDataClient(object):
    def __init__(self, client, treadmill_data_characteristic):
        self.treadmill_data_characteristic = treadmill_data_characteristic
        self.client = client
         
    async def start_treadmill_data_listener(self):
        return await self.client.start_notify(self.treadmill_data_characteristic, lambda sender, data: self.treadmill_data_handler(sender, data))

    async def stop_treadmill_data_listener(self):
        return await self.client.stop_notify(self.treadmill_data_characteristic)

    def treadmill_data_handler(self, sender, data):
        parsed_data = self.parse_treadmill_data(data)
        print(parsed_data)

    def parse_uint8(self, byte_array):
        return struct.unpack('B', bytes(byte_array[:1]))[0], byte_array[1:]

    def parse_uint16(self, byte_array):
        return struct.unpack('H', bytes(byte_array[:2]))[0], byte_array[2:]

    def parse_sint16(self, byte_array):
        return struct.unpack('h', bytes(byte_array[:2]))[0], byte_array[2:]

    def parse_treadmill_data(self, byte_array):
        print(f"Received data: {byte_array.hex()}")
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

async def scan():
    scanner = bleak.BleakScanner
    devices = await scanner.discover()
    return devices

async def connect(address):
    client = BleakClient(address)
    await client.connect()
    print("Connected to " + address)
    return client

async def get_all_characteristics(client):
    characteristics = []
    for service in client.services:
        print("[Service] {0}: {1} {2}".format(service.uuid, service.description, service.characteristics))
        for char in service.characteristics:
            characteristics.append(char)
    return characteristics

def print_characteristics(characteristics):
    for char in characteristics:
        print(
            "\t[Characteristic] {0}: (Handle: {1}) ({2}) | Name: {3}".format(
                char.uuid,
                char.handle,
                ",".join(char.properties),
                char.description,
            )
        )

def get_fitness_machine_control_point_characteristic(characteristics):
    for char in characteristics:
        if not char:
            continue    
        if char.uuid[:8] == "00002ad9":
            return char
    print("Fitness Machine Control Point characteristic not found")
    return None
    
def get_treadmill_data_characteristic(characteristics):
    for char in characteristics:
        if not char:
            continue    
        if char.uuid[:8] == "00002acd":
            return char
    print("Treadmill Data characteristic not found")
    return None
 
async def main():
    DEVICE_NAME = "EsangLinker"
    devices = await scan()
    walking_pad = None
    for device in devices:
        print(device)
        if(device.name == DEVICE_NAME):
            walking_pad = device
            print("Found walking pad:" + walking_pad.address + " " + walking_pad.name)
            print(walking_pad.details)
            break

    client = await connect(walking_pad.address)

    try: 
        characteristics = await get_all_characteristics(client)
        print_characteristics(characteristics)
        control_point_characteristic = get_fitness_machine_control_point_characteristic(characteristics)
        treadmill_data_characteristic = get_treadmill_data_characteristic(characteristics)
        control_point = FitnessMachineControlPoint(client, control_point_characteristic)
        treadmill_data_client = TreadmillDataClient(client, treadmill_data_characteristic)
        await control_point.set_speed(200)
        await treadmill_data_client.start_treadmill_data_listener()
        time.sleep(5)
        await treadmill_data_client.stop_treadmill_data_listener()
        await client.disconnect()

    except Exception as e:
        print(e)
        await client.disconnect()
        return




if __name__ == "__main__":
    asyncio.run(main())