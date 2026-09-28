// Part-6/src/UpdateRecord.jsx -- DATA-260 HW4, Part 1.III
//
// Rendered at "/update". Receives the record to edit and the update handler
// as props from App.jsx (not fetched independently -- see App.jsx's
// handleUpdate, which is what actually calls the backend and persists the
// change in MySQL). Falls back to redirecting home if no record was passed
// in (e.g. someone navigates to /update directly without picking a row).

import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

export default function UpdateRecord({ record, onUpdate }) {
  const navigate = useNavigate();
  const [courseCode, setCourseCode] = useState(record?.course_code || "");
  const [courseTitle, setCourseTitle] = useState(record?.course_title || "");
  const [error, setError] = useState("");

  if (!record) return <Navigate to="/" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await onUpdate(record.id, { course_code: courseCode, course_title: courseTitle });
      navigate("/");
    } catch (err) {
      setError(err.message || "Could not update course");
    }
  };

  return (
    <div className="card">
      <h1>Update Course #{record.id}</h1>
      {error && <div className="alert">{error}</div>}
      <form onSubmit={handleSubmit}>
        <label>
          Course Code
          <input
            value={courseCode}
            onChange={(e) => setCourseCode(e.target.value)}
            required
            autoFocus
          />
        </label>
        <label>
          Course Title
          <input
            value={courseTitle}
            onChange={(e) => setCourseTitle(e.target.value)}
            required
          />
        </label>
        <button type="submit">Save Changes</button>
      </form>
    </div>
  );
}
