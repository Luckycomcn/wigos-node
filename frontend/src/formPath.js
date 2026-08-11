export function getAtPath(obj, path) {
  return path.reduce((current, key) => (current == null ? current : current[key]), obj);
}

export function setAtPath(obj, path, value) {
  if (path.length === 0) return value;
  const [key, ...rest] = path;
  const isArray = Array.isArray(obj);
  const copy = isArray ? [...obj] : { ...obj };
  copy[key] = setAtPath(obj[key], rest, value);
  return copy;
}
