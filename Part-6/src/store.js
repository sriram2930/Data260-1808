// Part-6/src/store.js -- DATA-260 HW5, Part 1.III.1

import { configureStore } from "@reduxjs/toolkit";
import coursesReducer from "./coursesSlice";

export const store = configureStore({
  reducer: {
    courses: coursesReducer,
  },
});
