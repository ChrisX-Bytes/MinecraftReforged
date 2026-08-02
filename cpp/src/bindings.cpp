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
        .def("isDirty", &SubChunk::isDirty)
        .def("buildMesh", &SubChunk::buildMesh)
        .def_readwrite("faceVBO", &SubChunk::faceVBO)
        .def_readwrite("lineVBO", &SubChunk::lineVBO)
        .def_readwrite("faceCount", &SubChunk::faceCount)
        .def_readwrite("lineCount", &SubChunk::lineCount);

    py::class_<Chunk>(m, "Chunk")
        .def("getBlock", &Chunk::getBlock)
        .def("setBlock", &Chunk::setBlock)
        .def("getSubChunk", &Chunk::getSubChunk, py::return_value_policy::reference)
        .def("rebuildDirtySubChunks", &Chunk::rebuildDirtySubChunks)
        .def_readwrite("loadLevel", &Chunk::loadLevel)
        .def_readwrite("fluidLevels", &Chunk::fluidLevels)
        .def_readwrite("pendingFluids", &Chunk::pendingFluids);

    py::class_<FluidSimulator>(m, "FluidSimulator")
        .def(py::init<int>())
        .def("tick", &FluidSimulator::tick)
        .def("activate", &FluidSimulator::activate)
        .def("setSource", &FluidSimulator::setSource);

    py::class_<World>(m, "World")
        .def(py::init<>())
        .def("getChunk", &World::getChunk, py::return_value_policy::reference)
        .def("getBlock", &World::getBlock)
        .def("setBlock", &World::setBlock);
}
