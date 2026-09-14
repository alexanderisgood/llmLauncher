// CPU-only reproduction against the exact upstream range allocator. The ranges
// below are bookkeeping, not allocated model/GPU memory. Never call this a real
// inference-memory measurement. Set UZU_SOURCE to the pinned source checkout.
#[allow(dead_code)]
mod upstream {
    include!(concat!(env!("UZU_SOURCE"), "/crates/uzu-engine/src/backends/common/allocator/range_allocator.rs"));
}

use upstream::{AllocationType, RangeAllocator};

fn constants(pool: usize) -> AllocationType {
    // allocator.rs: non-reusable pool, cpu_available=true.
    AllocationType::Pooled { pool, can_alias_before: false, can_alias_after: true }
}

fn scratch(pool: usize) -> AllocationType {
    AllocationType::Pooled { pool, can_alias_before: true, can_alias_after: true }
}

fn retained_extent(chunks: usize, submit_every: usize) -> usize {
    let mut allocator = RangeAllocator::new(0..1024 * 1024);
    let mut pool = 0;
    let mut extent = 0;
    for chunk in 0..chunks {
        // A simplified RoPE/trie-constant lifetime followed by GPU scratch.
        let range = allocator.allocate_range_aligned(1024, 16, constants(pool)).unwrap();
        extent = extent.max(range.end);
        allocator.free_range(range, constants(pool));
        let range = allocator.allocate_range_aligned(1024, 16, scratch(pool)).unwrap();
        extent = extent.max(range.end);
        allocator.free_range(range, scratch(pool));
        if (chunk + 1) % submit_every == 0 {
            // Models dropping a pool only AFTER its submitted GPU work completes.
            allocator.free_pool(pool);
            pool += 1;
        }
    }
    allocator.free_pool(pool);
    assert!(allocator.is_empty());
    extent
}

#[test]
fn cpu_constants_cannot_reuse_prior_gpu_only_ranges() {
    assert_eq!(retained_extent(128, 128), 128 * 1024);
    assert_eq!(retained_extent(128, 8), 8 * 1024);
    assert_eq!(retained_extent(256, 8), 8 * 1024);
    println!("Synthetic retained range: 128 units in one pool; 8 with completed groups of 8.");
}

#[test]
fn fresh_pool_cannot_alias_an_in_flight_pool() {
    let mut allocator = RangeAllocator::new(0..8192);
    let old = allocator.allocate_range_aligned(1024, 16, constants(0)).unwrap();
    allocator.free_range(old.clone(), constants(0));
    let next = allocator.allocate_range_aligned(1024, 16, constants(1)).unwrap();
    assert_ne!(old, next);
    allocator.free_range(next, constants(1));
    allocator.free_pool(0);
    let reclaimed = allocator.allocate_range_aligned(1024, 16, constants(2)).unwrap();
    assert_eq!(old, reclaimed);
    allocator.free_range(reclaimed, constants(2));
    allocator.free_pool(1);
    allocator.free_pool(2);
    assert!(allocator.is_empty());
}

#[test]
#[should_panic(expected = "attempted to free a pool that has live allocations")]
fn pool_release_requires_all_chunk_allocations_to_be_dropped() {
    let mut allocator = RangeAllocator::new(0..8192);
    let _live = allocator.allocate_range_aligned(1024, 16, constants(0)).unwrap();
    allocator.free_pool(0);
}
