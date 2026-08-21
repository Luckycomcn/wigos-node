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

function isRequiredValueFilled(value) {
  return typeof value === "string" ? value.trim() !== "" : value != null;
}

// Recursively checks that every field marked `required` has a value, walking
// into nested "object" fields (rendered inline) and "array-object" fields
// (each entry must itself satisfy its own fields' required checks).
export function isFieldsetComplete(item, fields) {
  return fields.every((field) => {
    if (field.required && !isRequiredValueFilled(item?.[field.name])) return false;
    if (field.type === "object") {
      return isFieldsetComplete(item?.[field.name] || {}, field.fields);
    }
    if (field.type === "array-object") {
      return (item?.[field.name] || []).every((sub) => isFieldsetComplete(sub, field.fields));
    }
    return true;
  });
}
