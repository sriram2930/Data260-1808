// Part-6/src/Login.jsx -- DATA-260 HW4, Part 1.I
//
// Email + password login form. On success the backend has already set the
// HTTP-only session cookie (see api.js / AuthContext), so this component
// just needs to update the shared user state and redirect home.

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Login failed");
    }
  };

  return (
    <div className="card">
      <h1>Log in</h1>
      <p className="muted">Campus Course Catalogue &amp; Enrolment</p>
      {error && <div className="alert">{error}</div>}
      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="advisor@sjsu.edu"
            required
            autoFocus
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="course123"
            required
          />
        </label>
        <button type="submit">Log in</button>
      </form>
      <p className="muted small">Demo credentials: advisor@sjsu.edu / course123</p>
    </div>
  );
}
