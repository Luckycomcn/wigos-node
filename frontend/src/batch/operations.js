import * as affiliations from "./affiliations";
import * as configurations from "./configurations";
import * as wigosIds from "./wigosIds";

// The batch operations offered in the wizard, in the order they are listed.
// Each module exports `columns`, `toRows(entries)` and
// `applyRows(entries, rows, codelists)`; `addRows` is optional.
export const OPERATIONS = [
  {
    id: "affiliations",
    name: "op.programmeAffiliations",
    description: "op.programmeAffiliationsDescription",
    rowLabel: "op.programmeAffiliationsRows",
    module: affiliations,
  },
  {
    id: "configurations",
    name: "op.configurations",
    description: "op.configurationsDescription",
    rowLabel: "op.configurationsRows",
    module: configurations,
  },
  {
    id: "wigosIds",
    name: "op.wigosIds",
    description: "op.wigosIdsDescription",
    rowLabel: "op.wigosIdsRows",
    module: wigosIds,
  },
];

export const operationById = (id) => OPERATIONS.find((operation) => operation.id === id);

// Codelists an operation's columns need.
export const codelistsOf = (operation) => [
  ...new Set(operation.module.columns.filter((column) => column.codelist).map((column) => column.codelist)),
];
