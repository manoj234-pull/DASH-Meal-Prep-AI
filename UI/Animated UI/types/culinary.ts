export type ActiveScreen = 'plate' | 'dining' | 'ai' | 'weekly' | 'recipe' | 'grocery' | 'prep' | 'plans';
export type ViewportMode = 'auto' | 'desktop' | 'mobile';

export interface DailyScheduleItem {
  day: string;
  meals: string;
  sodium: string;
}
