// Part-6/src/Home.jsx -- DATA-260 HW5, Part 1.III.3
//
// Rendered at "/". HW4 received the course list as a prop from App.jsx; HW5
// reads it straight from Redux state with useSelector and dispatches
// fetchCourses itself whenever the logged-in user changes -- the list
// updates automatically when records are created, updated, or deleted
// because those thunks update the same Redux slice (see coursesSlice.js).

import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { useAuth } from "./AuthContext";
import { fetchCourses, clearCourses } from "./coursesSlice";

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { items: courses, status, error } = useSelector((state) => state.courses);

  useEffect(() => {
    if (user) {
      dispatch(fetchCourses());
    } else {
      dispatch(clearCourses());
    }
  }, [user, dispatch]);

  if (authLoading) return <p className="muted">Loading...</p>;

  if (!user) {
    return (
      <div className="card">
        <h1>Login required</h1>
        <p className="muted">
          You must be logged in to view the course catalogue.{" "}
          <Link to="/login">Log in</Link>
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="row-between">
        <h1>Campus Course Catalogue</h1>
        <Link to="/create" className="btn">
          Add Record
        </Link>
      </div>
      {error && <div className="alert">{error}</div>}
      {status === "loading" && <p className="muted">Loading courses...</p>}
      {status === "succeeded" && courses.length === 0 && <p className="muted">No courses yet.</p>}
      <ul className="record-list">
        {courses.map((c) => (
          <li key={c.id} className="card">
            <div className="row-between">
              <div>
                <strong>{c.course_code}</strong> - {c.course_title}
                {c.department && <span className="pill">{c.department}</span>}
              </div>
              <div className="actions">
                <button onClick={() => navigate(`/update/${c.id}`)}>Update</button>
                <button onClick={() => navigate(`/delete/${c.id}`)}>Delete</button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
