#include "gguf_lite.h"
#include "engine/stream.h"
#include <algorithm>
#include <cassert>
#include <fcntl.h>
#include <iostream>
#include <unistd.h>
#include <vector>
int main(int argc, char** argv) {
  assert(argc >= 2);
  gguf::File model; std::string err;
  bool ok=model.open_split(argv[1],err);
  if(argc==3 && std::string(argv[2])=="reject") {
    if(ok) { std::cerr<<"unexpected acceptance\n"; return 2; }
    std::cout<<"rejected: "<<err<<"\n"; return 0;
  }
  if(!ok) { std::cerr<<err<<"\n"; return 3; }
  strata::metal_engine::ExpertStream stream;
  if(!stream.open(model,err)) { std::cerr<<err<<"\n"; return 4; }
  size_t checked=0, reads=0;
  for(const auto& segment:model.segments) {
    gguf::File original;
    assert(original.open(segment.path,err));
    int fd=::open(segment.path.c_str(),O_RDONLY); assert(fd>=0);
    for(const auto& [name,t]:original.tensors) {
      auto combined=model.find(name); assert(combined);
      assert(combined->shape==t.shape && combined->type==t.type && combined->bytes==t.bytes);
      assert(combined->offset==segment.base+t.offset);
      uint64_t n=std::min<uint64_t>(4096,t.bytes); assert(n>0);
      std::vector<unsigned char> expected(n),actual(n);
      for(uint64_t at:{uint64_t(0),(t.bytes-n)/2,t.bytes-n}) {
        assert(::pread(fd,expected.data(),n,t.offset+at)==(ssize_t)n);
        assert(stream.read(actual.data(),n,combined->offset+at));
        assert(expected==actual);++reads;
      }
      ++checked;
    }
    ::close(fd);
    unsigned char b;
    if(segment.bytes % getpagesize()) assert(!stream.read(&b,1,segment.base+segment.bytes));
  }
  assert(checked==model.tensors.size());
  std::cout<<"PASS: "<<model.segments.size()<<" shards, "<<checked<<" tensor offsets/shapes/types, "<<reads<<" production SSD reads match original bytes\n";
}
