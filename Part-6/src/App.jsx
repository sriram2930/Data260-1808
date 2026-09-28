// Part-6/src/App.jsx -- DATA-260 HW4, Part 1.V
//
// Top-level component. Owns the shared `courses` list and `selectedCourse`
// state (useState), fetches the list on mount and whenever the logged-in
// user changes (useEffect), and passes callback props down to
// Create/Update/DeleteRecord rather than having each of them talk to the
// API independently -- per the assignment's "pass props for the Create,
// Update, and Delete components." Routing is react-router-dom.

import { useEffect, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./AuthContext";
import Home from "./Home";
import Login from "./Login";
import CreateRecord from "./CreateRecord";
import UpdateRecord from "./UpdateRecord";
import DeleteRecord from "./DeleteRecord";
import "./App.css";

export default function App() {
  const { user, logout } = useAuth();
  const [courses, setCourses] = useState([]);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const navigate = useNavigate();

  const refreshCourses = () => {
    if (!user) {
      setCourses([]);
      return;
    }
    api
      .listCourses()
      .then(setCourses)
      .catch((err) => setError(err.message));
  };

  useEffect(refreshCourses, [user]);

  const handleCreate = async (data) => {
    await api.createCourse(data);
    refreshCourses();
  };

  const handleUpdate = async (id, data) => {
    await api.updateCourse(id, data);
    refreshCourses();
  };

  const handleDelete = async (id) => {
    await api.deleteCourse(id);
    refreshCourses();
  };

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <div className="app">
      <nav className="navbar">
        <Link to="/" className="brand">
          Campus Course Catalogue
        </Link>
        <div>
          {user ? (
            <>
              <span className="muted small">Signed in as {user.name}</span>{" "}
              <button onClick={handleLogout}>Log out</button>
            </>
          ) : (
            <Link to="/login">Log in</Link>
          )}
        </div>
      </nav>
      <main>
        <Routes>
          <Route
            path="/"
            element={<Home courses={courses} error={error} onSelect={setSelected} />}
          />
          <Route path="/login" element={<Login />} />
          <Route path="/create" element={<CreateRecord onCreate={handleCreate} />} />
          <Route
            path="/update"
            element={<UpdateRecord record={selected} onUpdate={handleUpdate} />}
          />
          <Route
            path="/delete"
            element={<DeleteRecord record={selected} onDelete={handleDelete} />}
          />
        </Routes>
      </main>
    </div>
  );
}
