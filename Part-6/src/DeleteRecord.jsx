// Part-6/src/DeleteRecord.jsx -- DATA-260 HW5, Part 1.III.5
//
// Rendered at "/delete/:id". HW4 received the record and an onDelete
// callback as props from App.jsx; HW5 takes the id from the URL, looks the
// record up in Redux state, and dispatches the deleteCourse thunk directly
// on confirm -- Home.jsx's list updates automatically since both read the
// same Redux slice (see coursesSlice.js).

import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { deleteCourse } from "./coursesSlice";

export default function DeleteRecord() {
  const { id } = useParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const record = useSelector((state) =>
    state.courses.items.find((c) => String(c.id) === id)
  );
  const [error, setError] = useState("");

  if (!record) return <Navigate to="/" replace />;

  const handleDelete = async () => {
    setError("");
    const result = await dispatch(deleteCourse(record.id));
    if (deleteCourse.fulfilled.match(result)) {
      navigate("/");
    } else {
      setError(result.payload || "Could not delete course");
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
