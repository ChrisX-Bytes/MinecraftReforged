# fluid_simulator.py
import minecraft_core as mc

fluid_sim = None  # 在 main.py 中初始化

def init_fluid_simulator(updates_per_tick=40):
    global fluid_sim
    fluid_sim = mc.FluidSimulator(updates_per_tick)
    return fluid_sim