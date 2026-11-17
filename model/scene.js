import * as THREE from 'three';
import { D } from './helpers.js';
import { chassis, wheel, motorAssembly, caster, battery, cables, PCB_OFFSET_X } from './parts.js';
import { pcbAssembly, frontWall } from './electronics.js';

export { D, PCB_OFFSET_X };

/**
 * Builds the full maze-car in millimetres, Z-up, +X = front (sensor wall),
 * +Y = left, ground plane at z = 0.
 */
export function buildCar() {
  const car = new THREE.Group();
  car.name = 'MazeCar_1_1';

  car.add(chassis());

  const wall = frontWall();
  wall.name = 'SensorWall';
  car.add(wall);

  const pcb = pcbAssembly();
  pcb.position.set(PCB_OFFSET_X, 0, D.pcb.top);
  car.add(pcb);

  car.add(battery());

  for (const side of [-1, 1]) {
    const w = wheel();
    w.name = side > 0 ? 'Wheel_L' : 'Wheel_R';
    w.position.set(D.wheel.x, side * D.wheel.y, D.wheel.r);
    car.add(w);

    const m = motorAssembly(side);
    m.name = side > 0 ? 'Motor_L' : 'Motor_R';
    car.add(m);
  }

  car.add(caster(38, 0));
  car.add(caster(-58, 0));
  car.add(cables());

  car.updateMatrixWorld(true);
  return car;
}
