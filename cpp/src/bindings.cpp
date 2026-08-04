#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "world.h"
#include "fluid_simulator.h"

namespace py = pybind11;

PYBIND11_MODULE(minecraft_core, m) {
    m.doc() = "Minecraft Reforged C++ core";

    py::class_<SubChunk>(m, "SubChunk")
        .def("getBlock", &SubChunk::getBlock)
        .def("setBlock", &SubChunk::setBlock)
        .def("getWaterLevel", &SubChunk::getWaterLevel)
        .def("setWaterLevel", &SubChunk::setWaterLevel)
        .def("isDirty", &SubChunk::isDirty)
        .def("markDirty", &SubChunk::markDirty)
        .def("clearDirty", &SubChunk::clearDirty)
        .def("buildMesh", &SubChunk::buildMesh)
        .def("getYBase", &SubChunk::getYBase)
        .def_readwrite("faceVBO", &SubChunk::faceVBO)
        .def_readwrite("lineVBO", &SubChunk::lineVBO)
        .def_readwrite("faceCount", &SubChunk::faceCount)
        .def_readwrite("lineCount", &SubChunk::lineCount)
        .def_readwrite("lineVertices", &SubChunk::lineVertices);

    py::class_<Chunk>(m, "Chunk")
        .def("getBlock", &Chunk::getBlock)
        .def("setBlock", &Chunk::setBlock)
        .def("getWaterLevel", &Chunk::getWaterLevel)
        .def("setWaterLevel", &Chunk::setWaterLevel)
        .def("getSubChunk", &Chunk::getSubChunk, py::return_value_policy::reference)
        .def("rebuildDirtySubChunks", &Chunk::rebuildDirtySubChunks)
        .def_readwrite("loadLevel", &Chunk::loadLevel)
        .def_readwrite("isGenerated", &Chunk::isGenerated)
        .def_readwrite("fluidLevels", &Chunk::fluidLevels)
        .def_readwrite("pendingFluids", &Chunk::pendingFluids);

    // World 必须在 FluidSimulator 之前注册：FluidSimulator 构造接收 World*，
    // pybind 需 World 的转换器已就绪才能把 Python World 对象转成 C++ 指针。
    py::class_<World>(m, "World")
        .def(py::init<>())
        .def("getChunk", &World::getChunk, py::return_value_policy::reference)
        .def("getBlock", &World::getBlock)
        .def("setBlock", &World::setBlock)
        .def("getWaterLevel", &World::getWaterLevel)
        .def("setWaterLevel", &World::setWaterLevel);

    py::class_<FluidSimulator>(m, "FluidSimulator")
        .def(py::init<World*, int>(), py::arg("world") = nullptr, py::arg("updatesPerTick") = 40)
        .def("setWorld", &FluidSimulator::setWorld)
        .def("tick", &FluidSimulator::tick)
        .def("activate", &FluidSimulator::activate)
        .def("setSource", &FluidSimulator::setSource)
        .def("popDirtyChunks", &FluidSimulator::popDirtyChunks);
}
