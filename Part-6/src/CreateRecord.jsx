// Part-6/src/CreateRecord.jsx -- DATA-260 HW5, Part 1.III.4
//
// Rendered at "/create". HW4 received an onCreate callback prop from
// App.jsx; HW5 dispatches the createCourse thunk directly (see
// coursesSlice.js), which POSTs to the backend and appends the new row to
// Redux state -- Home.jsx picks that up automatically, no manual refetch.

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDispatch } from "react-redux";
import { createCourse } from "./coursesSlice";

export default function CreateRecord() {
  const [courseCode, setCourseCode] = useState("");
  const [courseTitle, setCourseTitle] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const dispatch = useDispatch();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const result = await dispatch(
      createCourse({ course_code: courseCode, course_title: courseTitle })
    );
    if (createCourse.fulfilled.match(result)) {
      navigate("/");
    } else {
      setError(result.payload || "Could not add course");
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
            placeholder="e.g. DATA-00260"
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
