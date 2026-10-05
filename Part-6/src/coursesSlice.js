// Part-6/src/coursesSlice.js -- DATA-260 HW5, Part 1.III.1-2
//
// Redux Toolkit slice for the primary domain entity (Course). Replaces the
// useState/useEffect data layer App.jsx owned in HW4 -- the course list now
// lives in the Redux store instead of component state, and components read
// it with useSelector instead of receiving it as a prop.

import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import axiosClient from "./axiosClient";

export const fetchCourses = createAsyncThunk("courses/fetchCourses", async () => {
  const res = await axiosClient.get("/courses");
  return res.data;
});

export const createCourse = createAsyncThunk(
  "courses/createCourse",
  async (data, { rejectWithValue }) => {
    try {
      const res = await axiosClient.post("/courses", data);
      return res.data;
    } catch (err) {
      return rejectWithValue(err.response?.data?.detail || err.message);
    }
  }
);

export const updateCourse = createAsyncThunk(
  "courses/updateCourse",
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const res = await axiosClient.put(`/courses/${id}`, data);
      return res.data;
    } catch (err) {
      return rejectWithValue(err.response?.data?.detail || err.message);
    }
  }
);

export const deleteCourse = createAsyncThunk(
  "courses/deleteCourse",
  async (id, { rejectWithValue }) => {
    try {
      await axiosClient.delete(`/courses/${id}`);
      return id;
    } catch (err) {
      return rejectWithValue(err.response?.data?.detail || err.message);
    }
  }
);

const coursesSlice = createSlice({
  name: "courses",
  initialState: {
    items: [],
    status: "idle", // idle | loading | succeeded | failed
    error: null,
  },
  reducers: {
    clearCourses(state) {
      state.items = [];
      state.status = "idle";
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCourses.pending, (state) => {
        state.status = "loading";
        state.error = null;
      })
      .addCase(fetchCourses.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.items = action.payload;
      })
      .addCase(fetchCourses.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.error.message;
      })
      .addCase(createCourse.fulfilled, (state, action) => {
        state.items.push(action.payload);
      })
      .addCase(createCourse.rejected, (state, action) => {
        state.error = action.payload || action.error.message;
      })
      .addCase(updateCourse.fulfilled, (state, action) => {
        const idx = state.items.findIndex((c) => c.id === action.payload.id);
        if (idx !== -1) state.items[idx] = action.payload;
      })
      .addCase(updateCourse.rejected, (state, action) => {
        state.error = action.payload || action.error.message;
      })
      .addCase(deleteCourse.fulfilled, (state, action) => {
        state.items = state.items.filter((c) => c.id !== action.payload);
      })
      .addCase(deleteCourse.rejected, (state, action) => {
        state.error = action.payload || action.error.message;
      });
  },
});

export const { clearCourses } = coursesSlice.actions;
export default coursesSlice.reducer;
