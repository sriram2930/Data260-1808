// Part-6/src/axiosClient.js -- DATA-260 HW5, Part 1.III.2
//
// Axios instance for the Redux thunks. withCredentials: true is axios's
// equivalent of fetch's credentials: "include" -- it's what makes the
// browser send the HttpOnly session cookie on cross-origin requests to the
// FastAPI backend (Vite dev server on :5173, API on :8008).

import axios from "axios";

const axiosClient = axios.create({
  baseURL: "http://localhost:8008/api",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export default axiosClient;
