// Transport-neutral DTOs for Unity JsonUtility. No game code or solver stubs.
using System;

namespace UnifiedPhysics {
    [Serializable] public sealed class Atmosphere {
        public double temperature_K, pressure_Pa, density_kg_m3, sound_speed_m_s, specific_heat_J_kg_K;
    }
    [Serializable] public sealed class Loads {
        public string frame;
        public double[] force_N, torque_N_m;
    }
    [Serializable] public sealed class MassProperties {
        public double mass_kg;
        public double[] center_of_mass_body_m;
        // Full inertia is a 3x3 array in JSON; use a JSON library supporting nested arrays.
    }
    [Serializable] public sealed class State {
        public string schema_version, module, frame, units;
        public double time_s, step_s, altitude_m, temperature_K;
        public double[] position_m, velocity_m_s;
        public Atmosphere atmosphere;
        public Loads loads;
        public MassProperties mass_properties;
    }
    public static class Coordinates {
        public static double[] NedPolarToUnity(double[] v) {
            if (v == null || v.Length != 3) throw new ArgumentException("Expected three components");
            return new[] {v[1], -v[2], v[0]};
        }
        public static double[] NedAxialToUnity(double[] v) {
            var result = NedPolarToUnity(v);
            for (int i = 0; i < 3; ++i) result[i] = -result[i];
            return result;
        }
    }
}
