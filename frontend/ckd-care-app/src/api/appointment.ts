import { api } from "./client";

export type AppointmentType = "CHECKUP" | "DIALYSIS" | "BLOOD_TEST" | "OTHER";
export interface AppointmentItem {
  id: number;
  appt_date: string;
  appt_time: string | null;
  appt_type: AppointmentType;
  hospital: string | null;
  note: string | null;
}
export interface OverviewResponse {
  next: { item: AppointmentItem; d_day: number } | null;
  upcoming: AppointmentItem[];
  past: AppointmentItem[];
}
export interface MonthResponse {
  year: number;
  month: number;
  items: AppointmentItem[];
}
export interface AppointmentInput {
  appt_date: string;
  appt_type: AppointmentType;
  appt_time?: string | null;
  hospital?: string | null;
  note?: string | null;
}

export const appointmentApi = {
  getOverview: () => api.get<OverviewResponse>("/records/appointments/overview"),
  getMonth: (year: number, month: number) =>
    api.get<MonthResponse>(`/records/appointments/month?year=${year}&month=${month}`),
  create: (body: AppointmentInput) =>
    api.post<AppointmentItem>("/records/appointments", body),
  update: (id: number, body: AppointmentInput) =>
    api.put<AppointmentItem>(`/records/appointments/${id}`, body),
  remove: (id: number) =>
    api.delete<{ ok: boolean }>(`/records/appointments/${id}`),
};
