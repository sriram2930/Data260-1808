// Part-6/src/AuthContext.jsx -- DATA-260 HW4, Part 1
//
// Shares the logged-in user across every component via React Context, so
// Home/CreateRecord/UpdateRecord/DeleteRecord can all check "are we logged
// in" without each one separately calling /api/me. useEffect below is what
// checks the existing session cookie once on app load (e.g. after a page
// refresh) so a refresh doesn't wrongly show "logged out".

import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const u = await api.login(email, password);
    setUser(u);
    return u;
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
