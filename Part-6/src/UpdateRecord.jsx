// Part-6/src/UpdateRecord.jsx -- DATA-260 HW5, Part 1.III.4
//
// Rendered at "/update/:id". HW4 received the record and an onUpdate
// callback as props from App.jsx; HW5 takes the id from the URL and looks
// the record up in Redux state with useSelector, then dispatches the
// updateCourse thunk directly on submit (see coursesSlice.js). Falls back to
// redirecting home if that id isn't in the store (e.g. a stale link, or a
// direct visit before the list has loaded).

import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { updateCourse } from "./coursesSlice";

export default function UpdateRecord() {
  const { id } = useParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const record = useSelector((state) =>
    state.courses.items.find((c) => String(c.id) === id)
  );
  const [courseCode, setCourseCode] = useState(record?.course_code || "");
  const [courseTitle, setCourseTitle] = useState(record?.course_title || "");
  const [error, setError] = useState("");

  if (!record) return <Navigate to="/" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    const result = await dispatch(
      updateCourse({ id: record.id, data: { course_code: courseCode, course_title: courseTitle } })
    );
    if (updateCourse.fulfilled.match(result)) {
      navigate("/");
    } else {
      setError(result.payload || "Could not update course");
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
