#pragma once
#include <cstdint>

using BlockID = uint16_t;

constexpr BlockID BLOCK_AIR = 0;
constexpr BlockID BLOCK_STONE = 1;
constexpr BlockID BLOCK_GRASS_BLOCK = 2;
constexpr BlockID BLOCK_DIRT = 3;
constexpr BlockID BLOCK_WOOD = 4;
constexpr BlockID BLOCK_LEAVES = 5;
constexpr BlockID BLOCK_SAND = 6;
constexpr BlockID BLOCK_SNOW = 7;
constexpr BlockID BLOCK_BEDROCK = 8;
constexpr BlockID BLOCK_WATER = 9;
// 世界常量 
constexpr int CHUNK_SIZE = 16;
constexpr int CHUNK_HEIGHT = 384;
constexpr int WORLD_BOTTOM = -64;
constexpr int LOAD_LEVEL_UNLOADED = 45;
constexpr int NUM_SECTIONS = CHUNK_HEIGHT / 16; // 24
