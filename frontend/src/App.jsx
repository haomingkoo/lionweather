import { LocationsProvider } from "./hooks/useLocations.jsx";
import { ThemeProvider } from "./contexts/ThemeContext";
import { Dashboard } from "./pages/Dashboard";

export function App() {
  return (
    <ThemeProvider>
      <LocationsProvider>
        <Dashboard />
      </LocationsProvider>
    </ThemeProvider>
  );
}
