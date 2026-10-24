#include <cmath>
#include <iomanip>
#include <iostream>
#include "chrono/physics/ChSystemNSC.h"
#include "chrono/physics/ChBody.h"

int main() {
    chrono::ChSystemNSC system;
    // NED: gravity acts in positive Z. No collision geometry is needed for free fall.
    system.SetGravitationalAcceleration(chrono::ChVector3d(0, 0, 9.80665));
    auto body = chrono_types::make_shared<chrono::ChBody>();
    body->SetMass(2.0);
    body->SetInertiaXX(chrono::ChVector3d(1, 1, 1));
    body->SetPos(chrono::ChVector3d(0, 0, 0));
    system.AddBody(body);
    constexpr double dt = 0.001;
    for (int i = 0; i < 1000; ++i) system.DoStepDynamics(dt);
    auto p = body->GetPos();
    auto v = body->GetPosDt();
    if (std::abs(p.z() - 4.903325) > 0.02 || std::abs(v.z() - 9.80665) > 1e-6) {
        std::cerr << "Chrono free fall failed: " << p.z() << ", " << v.z() << '\n';
        return 1;
    }
    std::cout << std::setprecision(16)
              << "{\"time_s\":" << system.GetChTime() << ",\"step_s\":" << dt
              << ",\"position_m\":[" << p.x() << ',' << p.y() << ',' << p.z()
              << "],\"velocity_m_s\":[" << v.x() << ',' << v.y() << ',' << v.z()
              << "],\"mass_kg\":2}\n";
}
