export interface Lap{index:number;startElapsedSeconds:number;endElapsedSeconds:number;durationSeconds:number}
export interface Activity{activityId:string;sourcePath:string;durationSeconds:number;recordCount:number;hasPower:boolean;hasHeartRate:boolean;laps:Lap[];extractable:boolean;exclusionReason:string|null}
export interface Inventory{datasetPath:string;extractable:Activity[];excluded:Activity[]}
export interface Point{elapsedSeconds:number;power:number|null;heartRate:number|null;powerWKg?:number|null;hrPctMax?:number|null;hrPctThreshold?:number|null}
export interface Norm{weightKg:number|null;hrMaxBpm:number|null;hrThresholdBpm:number|null;normalizePower:boolean;normalizeHrMax:boolean;normalizeHrThreshold:boolean}
