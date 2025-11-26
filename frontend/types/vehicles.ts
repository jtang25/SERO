// types/vehicles.ts

export type FleetType = "fire" | "police";

export type TripPoint = {
  time: number; // seconds since start
  lon: number;
  lat: number;
};

export type TripType = "fire_truck" | "ambulance" | "police_car";

export type Trip = {
  id: string;
  fleet_type: FleetType;
  type: TripType;
  side: "friendly" | "enemy";
  path: TripPoint[];
};

export type GridCell = {
  id: string;
  cellId: number;
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
  risk: number; // 0..1
};

export type StationInput = {
  station_id: string;
  lat: number;
  lon: number;
  vehicles_current: number;
};

export type StationDeployment = {
  station_id: string;
  lat: number;
  lon: number;
  vehicles_current: number;
  vehicles_target: number;
  local_risk: number;
};

export type Station = StationDeployment & {
  fleet_type: FleetType;
};

export type Move = {
  from_station_id: string;
  to_station_id: string;
  num_vehicles: number;
  distance: number;
};

export type DeploymentResponse = {
  fleet_type: FleetType | string;
  timestamp: string;
  stations: StationDeployment[];
  moves: Move[];
  total_travel_cost: number;
};

export type RiskApiCell = {
  cell_id: number;
  risk_score: number;
  lat: number;
  lon: number;
};
