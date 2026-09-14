// Deliberately incomplete fixture, never used by the launcher.
class TTLCache {
  constructor(capacity, now = Date.now) {
    this.capacity = capacity;
    this.now = now;
    this.entries = new Map();
  }
  set(key, value, ttl) {
    this.entries.set(key, {value, expires: this.now() + ttl});
    if (this.entries.size > this.capacity) this.entries.delete(this.entries.keys().next().value);
  }
  get(key) {
    const entry = this.entries.get(key);
    return entry && entry.value;
  }
  get size() { return this.entries.size; }
}
module.exports = {TTLCache};
