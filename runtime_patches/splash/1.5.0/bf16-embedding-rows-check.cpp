// CPU-only regression for Flash-Next's 160-value original BF16 PLE rows.
#include "metal/abi/Gguf.h"
#include "model/GgufFile.hpp"
#include "model/GgufImage.hpp"
#include "model/GgufImageLayout.hpp"
#include <cassert>
#include <iostream>

static_assert(gguf_embedding_block_elements(GGUF_FMT_BF16) == 1);
static_assert(gguf_embedding_row_bytes(GGUF_FMT_BF16, 160) == 320);
static_assert(gguf_embedding_row_bytes(GGUF_FMT_F16, 160) == 320);
static_assert(gguf_embedding_block_elements(GGUF_FMT_Q4K) == 256);
static_assert(gguf_embedding_row_bytes(GGUF_FMT_Q4K, 256) == 144);
static_assert(splash::model::ggufRowBytes(kQuantFormats[GGUF_FMT_BF16], 256) == 512);

int main(int argc, char **argv) {
  assert(argc == 2);
  splash::model::OpenGguf opened({argv[1]});
  const auto rows = splash::model::gguf::tableRows(opened.file(), "per_layer_token_embd.weight", 160);
  assert(rows.rows == 2);
  assert(rows.rowBytes == 320);
  assert(opened.file().require("per_layer_token_embd.weight").bytes == 640);
  opened.checkUnchanged();
  std::cout << "CPU BF16 PLE rows: 160 columns, 320 bytes per row; Q4 projection layout unchanged\n";
}
