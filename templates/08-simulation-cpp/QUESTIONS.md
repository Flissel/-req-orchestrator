# 📋 Simulation System (C++) - Projekt-Fragebogen
## Template: 08-simulation-cpp (C++20 + CMake + Google Test)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Projekt Name** | |
| **Simulations-Typ** | Physik, Wirtschaft, Biologie, Netzwerk |
| **Zielplattform** | Linux, Windows, Cross-Platform |

---

## A. SIMULATIONS-DOMÄNE

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| A1 | Was wird simuliert? | Partikel, Agenten, Systeme | |
| A2 | Zeitdiskret/Kontinuierlich? | Ticks vs. Differentialgleichungen | |
| A3 | Räumlich? | 2D, 3D, keine Geometrie | |
| A4 | Agenten-Anzahl? | 100, 10.000, 1.000.000+ | |
| A5 | Simulations-Dauer? | Sekunden, Stunden, Tage | |

---

## B. PHYSIK & MATHEMATIK

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| B1 | Numerische Methoden? | [ ] Euler [ ] Runge-Kutta [ ] Verlet [ ] Custom | |
| B2 | Lineare Algebra? | [ ] Eigen (empfohlen) [ ] GLM [ ] Custom | |
| B3 | Random Number Generator? | [ ] std::mt19937 [ ] PCG [ ] Custom | |
| B4 | Kollisionserkennung? | [ ] Keine [ ] AABB [ ] SAT [ ] GJK | |
| B5 | Physik-Engine? | [ ] Keine [ ] Bullet [ ] Box2D [ ] Custom | |

---

## C. PERFORMANCE REQUIREMENTS

| # | Frage | Antwort |
|---|-------|---------|
| C1 | Target FPS? | 60, Real-time, As fast as possible |
| C2 | Max Speicherverbrauch? | GB |
| C3 | Parallelisierung nötig? | Threads, GPU |
| C4 | Precision? | float, double |
| C5 | Determinismus? | Reproduzierbare Ergebnisse |

---

## D. TECH-STACK ENTSCHEIDUNGEN

### Build System

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | Build System? | [ ] CMake (default) [ ] Meson [ ] Bazel | |
| D2 | C++ Standard? | [ ] C++20 (empfohlen) [ ] C++17 [ ] C++23 | |
| D3 | Compiler? | [ ] GCC [ ] Clang [ ] MSVC [ ] All | |
| D4 | Package Manager? | [ ] vcpkg (empfohlen) [ ] Conan [ ] None | |

### Parallelisierung

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D5 | Threading? | [ ] std::thread [ ] OpenMP [ ] TBB | |
| D6 | GPU Computing? | [ ] Keine [ ] CUDA [ ] OpenCL [ ] Vulkan Compute | |
| D7 | SIMD? | [ ] Auto [ ] SSE [ ] AVX2 [ ] AVX-512 | |

### Visualisierung

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D8 | Visualisierung? | [ ] Keine [ ] Terminal [ ] SDL2 [ ] OpenGL [ ] Vulkan | |
| D9 | GUI Framework? | [ ] Keine [ ] Dear ImGui [ ] Qt [ ] wxWidgets | |
| D10 | Plotting? | [ ] Keine [ ] matplotplusplus [ ] gnuplot | |

### I/O & Daten

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D11 | Config Format? | [ ] JSON [ ] YAML [ ] TOML [ ] INI | |
| D12 | Output Format? | [ ] CSV [ ] HDF5 [ ] Binary [ ] VTK | |
| D13 | Logging? | [ ] spdlog (empfohlen) [ ] glog [ ] Custom | |

---

## E. TESTING & QUALITÄT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Unit Testing? | [ ] Google Test (default) [ ] Catch2 [ ] doctest | |
| E2 | Benchmarking? | [ ] Keine [ ] Google Benchmark [ ] nanobench | |
| E3 | Coverage? | [ ] Keine [ ] gcov [ ] llvm-cov | |
| E4 | Static Analysis? | [ ] Keine [ ] clang-tidy [ ] cppcheck | |
| E5 | Sanitizers? | [ ] AddressSanitizer [ ] UBSan [ ] ThreadSanitizer | |

---

## F. ENTWICKLUNGSUMGEBUNG

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| F1 | IDE? | [ ] VS Code [ ] CLion [ ] Visual Studio [ ] Vim | |
| F2 | Debugger? | [ ] GDB [ ] LLDB [ ] Visual Studio | |
| F3 | Profiler? | [ ] perf [ ] Valgrind [ ] VTune [ ] Tracy | |
| F4 | Dev Container? | [ ] Ja [ ] Nein | |

---

## G. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Distribution? | [ ] Source [ ] Binary [ ] Docker | |
| G2 | Static/Dynamic Linking? | [ ] Static [ ] Dynamic | |
| G3 | Installer? | [ ] Keine [ ] NSIS [ ] CPack | |
| G4 | CI/CD? | [ ] GitHub Actions [ ] GitLab CI | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] CMakeLists.txt
- [ ] Project Structure
- [ ] Core Simulation Loop
- [ ] Entity/Agent Classes
- [ ] Math Utilities
- [ ] Config Parser
- [ ] Visualization Setup
- [ ] Unit Tests
- [ ] Benchmarks
- [ ] Docker Setup

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "08-simulation-cpp",
  "build": {
    "system": "CMake 3.20+",
    "standard": "C++20",
    "package_manager": "vcpkg"
  },
  "libraries": {
    "math": "Eigen",
    "testing": "Google Test",
    "logging": "spdlog",
    "json": "nlohmann/json"
  },
  "performance": {
    "threading": "OpenMP / TBB",
    "simd": "Auto-vectorization"
  },
  "visualization": {
    "graphics": "SDL2 / OpenGL",
    "gui": "Dear ImGui"
  }
}
```
