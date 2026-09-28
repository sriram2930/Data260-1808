// Part-6/src/api.js -- DATA-260 HW4, Part 1
//
// Thin fetch wrapper for the FastAPI backend (Part-1/, running on PORT_BASE
// 8008). credentials: "include" on every call is what makes the browser
// actually send the HttpOnly session cookie back on cross-origin requests
// (the Vite dev server runs on :5173, the API on :8008), which is also why
// the backend's CORS config needs allow_credentials=True with an explicit
// origin instead of "*".

const API_BASE = "http://localhost:8008/api";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON, keep statusText
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (email, password) =>
    request("/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request("/me"),
  logout: () => request("/logout", { method: "POST" }),

  listCourses: () => request("/courses"),
  getCourse: (id) => request(`/courses/${id}`),
  createCourse: (data) => request("/courses", { method: "POST", body: JSON.stringify(data) }),
  updateCourse: (id, data) =>
    request(`/courses/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteCourse: (id) => request(`/courses/${id}`, { method: "DELETE" }),
};
