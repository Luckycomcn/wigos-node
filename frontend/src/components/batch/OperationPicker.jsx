import { OPERATIONS } from "../../batch/operations";

export default function OperationPicker({ stationCount, onPick }) {
  return (
    <div>
      <p className="batch-intro">
        Choose what to change in the {stationCount} selected {stationCount === 1 ? "station" : "stations"}. The next step
        shows their current values in a spreadsheet you can edit, or export to Excel and import back.
      </p>
      <div className="operation-cards">
        {OPERATIONS.map((operation) => (
          <button key={operation.id} type="button" className="operation-card" onClick={() => onPick(operation)}>
            <span className="operation-card-name">{operation.name}</span>
            <span className="operation-card-description">{operation.description}</span>
            <span className="operation-card-rows">{operation.rowLabel}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
