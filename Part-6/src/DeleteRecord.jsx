// Part-6/src/DeleteRecord.jsx -- DATA-260 HW4, Part 1.IV
//
// Rendered at "/delete". Receives the record to delete and the delete
// handler as props from App.jsx. A single confirm button; on click it calls
// the backend (removing the row from MySQL) and redirects home.

import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

export default function DeleteRecord({ record, onDelete }) {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  if (!record) return <Navigate to="/" replace />;

  const handleDelete = async () => {
    setError("");
    try {
      await onDelete(record.id);
      navigate("/");
    } catch (err) {
      setError(err.message || "Could not delete course");
    }
  };

  return (
    <div className="card">
      <h1>Delete Course</h1>
      <p>
        Delete <strong>{record.course_code}</strong> - {record.course_title}?
      </p>
      {error && <div className="alert">{error}</div>}
      <div className="actions">
        <button className="danger" onClick={handleDelete}>
          Delete
        </button>
        <button onClick={() => navigate("/")}>Cancel</button>
      </div>
    </div>
  );
}
