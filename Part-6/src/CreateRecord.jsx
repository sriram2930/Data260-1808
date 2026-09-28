// Part-6/src/CreateRecord.jsx -- DATA-260 HW4, Part 1.II
//
// Rendered at "/create". Primary field (course code) + secondary field
// (course title) inputs, plus a domain-appropriate submit button. Receives
// the create handler as a prop from App.jsx -- on submit it calls that prop,
// which POSTs to the backend (MySQL assigns the auto-incremented id, not
// generated client-side), then this redirects home so the updated list is
// visible.

import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function CreateRecord({ onCreate }) {
  const [courseCode, setCourseCode] = useState("");
  const [courseTitle, setCourseTitle] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await onCreate({ course_code: courseCode, course_title: courseTitle });
      navigate("/");
    } catch (err) {
      setError(err.message || "Could not add course");
    }
  };

  return (
    <div className="card">
      <h1>Add a Course</h1>
      {error && <div className="alert">{error}</div>}
      <form onSubmit={handleSubmit}>
        <label>
          Course Code
          <input
            value={courseCode}
            onChange={(e) => setCourseCode(e.target.value)}
            placeholder="e.g. DATA-260"
            required
            autoFocus
          />
        </label>
        <label>
          Course Title
          <input
            value={courseTitle}
            onChange={(e) => setCourseTitle(e.target.value)}
            placeholder="e.g. Big Data Technologies and Systems"
            required
          />
        </label>
        <button type="submit">Submit Course Listing</button>
      </form>
    </div>
  );
}
