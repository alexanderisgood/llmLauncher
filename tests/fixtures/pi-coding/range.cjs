function sumRange(start, end) {
  if (!Number.isInteger(start) || !Number.isInteger(end)) throw new TypeError('Integers required');
  let result = 0;
  for (let i = start; i < end; i++) result += i;
  return result;
}
module.exports = {sumRange};
