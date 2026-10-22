type Job = {status:string;cancel_requested?:boolean;content_decision?:string|null;content_approved?:boolean};
export const ACTIVE_JOB_STATES: string[];
export function activeBusinessJobs(jobs?: Job[]): boolean;
export function businessJobLabel(job: Job): string;
export function businessProgress(jobs?: Job[]): {active:number;pendingCancel:number;waitingReview:number;approved:number;needsRework:number};
export function pollBusinessOperations(jobs: Job[], state:{visible:boolean;online:boolean;unknown:boolean;busy:boolean}): boolean;
