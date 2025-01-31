import asyncio
import bleak
import time
from bleak import BleakClient

class FitnessMachineControlPoint(object):
    def __init__(self, client, machine_control_point_characteristic, treadmill_data_characteristic):
        self.machine_control_point_characteristic = machine_control_point_characteristic
        self.treadmill_data_characteristic = treadmill_data_characteristic
        self.client = client
            
    async def send_resume_command(self):
        await self.client.write_gatt_char(self.machine_control_point_characteristic, bytearray([0x07]), response=False)

    async def send_pause_command(self):
        await self.client.write_gatt_char(self.machine_control_point_characteristic, bytearray([0x08, 0x02]), response=False)

    async def send_stop_command(self):
        await self.client.write_gatt_char(self.machine_control_point_characteristic, bytearray([0x08, 0x01]), response=False)

    async def set_speed(self, speed):
        speed_bytes = speed.to_bytes(2, byteorder='little')
        print(speed_bytes)
        await self.client.write_gatt_char(self.machine_control_point_characteristic, bytearray([0x02, speed_bytes[0], speed_bytes[1]]), response=False)

    async def start_treadmill_data_listener(self):
        return await self.client.start_notify(self.treadmill_data_characteristic, treadmill_data_handler)

    async def stop_treadmill_data_listener(self):
        return await self.client.stop_notify(self.treadmill_data_characteristic)

def treadmill_data_handler(sender, data):
    print("Data received: {0}".format(data))

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
            print("Found waling pad:" + walking_pad.address + " " + walking_pad.name)
            print(walking_pad.details)
            break

    client = await connect(walking_pad.address)

    try: 
        characteristics = await get_all_characteristics(client)
        print_characteristics(characteristics)
        control_point_characteristic = get_fitness_machine_control_point_characteristic(characteristics)
        treadmill_data_characteristic = get_treadmill_data_characteristic(characteristics)
        control_point = FitnessMachineControlPoint(client, control_point_characteristic, treadmill_data_characteristic)
        await control_point.set_speed(200)
        await control_point.start_treadmill_data_listener()
        time.sleep(10)
        await control_point.stop_treadmill_data_listener()
        await client.disconnect()

    except Exception as e:
        print(e)
        await client.disconnect()
        return




if __name__ == "__main__":
    asyncio.run(main())