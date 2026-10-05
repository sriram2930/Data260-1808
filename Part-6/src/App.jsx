// Part-6/src/App.jsx -- DATA-260 HW5, Part 1.III.1
//
// Top-level component. HW4 had App.jsx own the course list in useState and
// pass callback props down to Create/Update/DeleteRecord. HW5 moves that
// data layer to Redux (see store.js / coursesSlice.js): the list now lives
// in the Redux store, each screen reads it with useSelector and dispatches
// thunks directly instead of going through App-owned callbacks. App.jsx is
// left owning only routing and the navbar. Update/Delete now take the record
// id from the URL (/update/:id, /delete/:id) instead of an App-level
// "selected" prop, since the record can be looked up from the store by id.

import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import Home from "./Home";
import Login from "./Login";
import CreateRecord from "./CreateRecord";
import UpdateRecord from "./UpdateRecord";
import DeleteRecord from "./DeleteRecord";
import "./App.css";

export default function App() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/create" element={<CreateRecord />} />
          <Route path="/update/:id" element={<UpdateRecord />} />
          <Route path="/delete/:id" element={<DeleteRecord />} />
        </Routes>
      </main>
    </div>
  );
}
