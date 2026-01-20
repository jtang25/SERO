export type ChatContext = {
  map?: {
    center: { lat: number; lon: number };
    zoom: number;
    pitch: number;
    bearing: number;
  };
  focused_cell_id?: number | null;
  selected_cell_id?: number | null;
  selected_station?: {
    station_id: string;
    name?: string;
    fleet_type?: string;
    lat: number;
    lon: number;
    in_move?: boolean;
  } | null;
  selected_trip?: {
    id: string;
    fleet_type?: string;
    from_station_id?: string;
    to_station_id?: string;
  } | null;
  deployment?: {
    station_ids: string[];
    moving_station_ids: string[];
    moves: {
      from_station_id: string;
      to_station_id: string;
      fleet_type?: string;
    }[];
  };
};
