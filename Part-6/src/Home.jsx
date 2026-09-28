// Part-6/src/Home.jsx -- DATA-260 HW4, Part 1.I
//
// Rendered at the root route "/". Receives the course list and a "select
// this record" callback as props from App.jsx (App owns the useEffect that
// actually fetches the list). Only logged-in users see the list or the Add
// Record button -- logged-out users see a "Login required" message instead,
// per the assignment.

import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function Home({ courses, error, onSelect }) {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

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

  const goTo = (path, course) => {
    onSelect(course);
    navigate(path);
  };

  return (
    <div>
      <div className="row-between">
        <h1>Campus Course Catalogue</h1>
        <Link to="/create" className="btn">
          Add Record
        </Link>
      </div>
      {error && <div className="alert">{error}</div>}
      {courses.length === 0 && <p className="muted">No courses yet.</p>}
      <ul className="record-list">
        {courses.map((c) => (
          <li key={c.id} className="card">
            <div className="row-between">
              <div>
                <strong>{c.course_code}</strong> - {c.course_title}
                {c.department && <span className="pill">{c.department}</span>}
              </div>
              <div className="actions">
                <button onClick={() => goTo("/update", c)}>Update</button>
                <button onClick={() => goTo("/delete", c)}>Delete</button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
