#pragma once

#include <hpx/execution.hpp>
#include <cstddef>
#include <cstdint>

namespace hpyx::policy {

enum class Kind : std::uint8_t { seq, par, par_unseq, unseq };
enum class ChunkKind : std::uint8_t { none, static_, dynamic_, auto_, guided };

struct PolicyToken {
    Kind kind;
    bool task;
    ChunkKind chunk;
    std::size_t chunk_size;
};

template <typename Fn>
auto dispatch_policy(PolicyToken t, Fn&& fn) {
    namespace ex = hpx::execution;

    auto with_chunk = [&](auto&& pol) {
        switch (t.chunk) {
        case ChunkKind::none:
            return fn(pol);
        case ChunkKind::static_:
            return fn(pol.with(ex::static_chunk_size(t.chunk_size)));
        case ChunkKind::dynamic_:
            return fn(pol.with(ex::dynamic_chunk_size(t.chunk_size)));
        case ChunkKind::auto_:
            return fn(pol.with(ex::auto_chunk_size()));
        case ChunkKind::guided:
            return fn(pol.with(ex::guided_chunk_size()));
        }
        return fn(pol);
    };

    if (t.task) {
        switch (t.kind) {
        case Kind::seq:
            return with_chunk(ex::seq(ex::task));
        case Kind::par:
            return with_chunk(ex::par(ex::task));
        case Kind::par_unseq:
            return with_chunk(ex::par_unseq(ex::task));
        case Kind::unseq:
            return with_chunk(ex::unseq);  // no task variant
        }
    } else {
        switch (t.kind) {
        case Kind::seq:
            return with_chunk(ex::seq);
        case Kind::par:
            return with_chunk(ex::par);
        case Kind::par_unseq:
            return with_chunk(ex::par_unseq);
        case Kind::unseq:
            return with_chunk(ex::unseq);
        }
    }
    // Unreachable — but makes the compiler happy.
    return with_chunk(ex::seq);
}

}  // namespace hpyx::policy
