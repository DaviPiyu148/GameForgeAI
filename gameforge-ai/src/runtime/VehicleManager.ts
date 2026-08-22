import Phaser from 'phaser';
import type { VehicleDef } from './types';

export interface VehicleInstance {
  def: VehicleDef;
  sprite: Phaser.Physics.Arcade.Sprite;
  currentSpeed: number;
  headingAngle: number;
}

export class VehicleManager {
  private scene: Phaser.Scene;
  private vehicleGroup: Phaser.Physics.Arcade.Group;
  private vehicleMap: Map<string, VehicleInstance> = new Map();
  private occupiedVehicle: VehicleInstance | null = null;
  private onVehicleEnter?: (vehicle: VehicleDef) => void;
  private onVehicleExit?: (vehicle: VehicleDef) => void;

  constructor(
    scene: Phaser.Scene,
    onVehicleEnter?: (vehicle: VehicleDef) => void,
    onVehicleExit?: (vehicle: VehicleDef) => void
  ) {
    this.scene = scene;
    this.vehicleGroup = this.scene.physics.add.group();
    this.onVehicleEnter = onVehicleEnter;
    this.onVehicleExit = onVehicleExit;
  }

  public spawnVehicles(vehicles: VehicleDef[], activeRegionId: string): void {
    // Clear existing
    this.vehicleGroup.clear(true, true);
    this.vehicleMap.clear();
    this.occupiedVehicle = null;

    for (const v of vehicles) {
      if (v.region_id !== activeRegionId) continue;

      const spr = this.vehicleGroup.create(v.x, v.y, 'tex_vehicle') as Phaser.Physics.Arcade.Sprite;
      const w = v.width || 48;
      const h = v.height || 28;
      spr.setDisplaySize(w, h);
      spr.setCollideWorldBounds(true);
      if (v.color) {
        spr.setTint(Phaser.Display.Color.HexStringToColor(v.color).color);
      }
      (spr.body as Phaser.Physics.Arcade.Body).setAllowGravity(false);
      (spr.body as Phaser.Physics.Arcade.Body).setDrag(200, 200);

      this.vehicleMap.set(v.id, {
        def: v,
        sprite: spr,
        currentSpeed: 0,
        headingAngle: 0,
      });
    }
  }

  public getOccupiedVehicle(): VehicleInstance | null {
    return this.occupiedVehicle;
  }

  public isInVehicle(): boolean {
    return this.occupiedVehicle !== null;
  }

  public getNearbyVehicle(x: number, y: number, radius: number = 64): VehicleInstance | null {
    for (const vInst of this.vehicleMap.values()) {
      const dist = Phaser.Math.Distance.Between(x, y, vInst.sprite.x, vInst.sprite.y);
      if (dist <= radius) {
        return vInst;
      }
    }
    return null;
  }

  public enterVehicle(vInst: VehicleInstance, playerSprite: Phaser.Physics.Arcade.Sprite): boolean {
    if (this.occupiedVehicle) return false;

    this.occupiedVehicle = vInst;
    vInst.def.is_occupied = true;
    playerSprite.setVisible(false);
    (playerSprite.body as Phaser.Physics.Arcade.Body).enable = false;

    if (this.onVehicleEnter) {
      this.onVehicleEnter(vInst.def);
    }
    return true;
  }

  public exitVehicle(playerSprite: Phaser.Physics.Arcade.Sprite): VehicleDef | null {
    if (!this.occupiedVehicle) return null;

    const vInst = this.occupiedVehicle;
    vInst.def.is_occupied = false;

    // Position player safely offset to the left or right of vehicle
    const exitX = Math.max(32, Math.min(this.scene.physics.world.bounds.width - 32, vInst.sprite.x + 36));
    const exitY = Math.max(32, Math.min(this.scene.physics.world.bounds.height - 32, vInst.sprite.y));

    playerSprite.setPosition(exitX, exitY);
    playerSprite.setVisible(true);
    (playerSprite.body as Phaser.Physics.Arcade.Body).enable = true;
    (playerSprite.body as Phaser.Physics.Arcade.Body).setVelocity(0, 0);

    const exitedDef = vInst.def;
    this.occupiedVehicle = null;

    if (this.onVehicleExit) {
      this.onVehicleExit(exitedDef);
    }
    return exitedDef;
  }

  public updateDriving(
    moveX: number,
    moveY: number,
    playerSprite: Phaser.Physics.Arcade.Sprite,
    delta: number
  ): void {
    if (!this.occupiedVehicle) return;

    const vInst = this.occupiedVehicle;
    const body = vInst.sprite.body as Phaser.Physics.Arcade.Body;
    const maxSpeed = vInst.def.max_speed || 450;
    const accel = (vInst.def.acceleration || 400) * (delta / 1000);
    const handling = vInst.def.handling || 2.5;

    if (moveX !== 0 || moveY !== 0) {
      const targetAngle = Math.atan2(moveY, moveX);
      vInst.headingAngle = Phaser.Math.Angle.RotateTo(vInst.headingAngle, targetAngle, handling * (delta / 1000) * Math.PI);
      vInst.currentSpeed = Math.min(maxSpeed, vInst.currentSpeed + accel);
    } else {
      vInst.currentSpeed = Math.max(0, vInst.currentSpeed - accel * 1.5);
    }

    const vx = Math.cos(vInst.headingAngle) * vInst.currentSpeed;
    const vy = Math.sin(vInst.headingAngle) * vInst.currentSpeed;

    body.setVelocity(vx, vy);
    vInst.sprite.setRotation(vInst.headingAngle);

    // Sync player position with vehicle for camera follow
    playerSprite.setPosition(vInst.sprite.x, vInst.sprite.y);
  }

  public getVehicleGroup(): Phaser.Physics.Arcade.Group {
    return this.vehicleGroup;
  }
}
