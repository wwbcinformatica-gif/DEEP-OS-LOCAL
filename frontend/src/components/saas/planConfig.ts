// Plan configuration - which features each plan has access to
// Keys MUST match PlanType enum in backend/models/plan.py (English: free, monthly, quarterly, annual)
export const planFeatures: Record<string, string[]> = {
  free: [
    'plans',
    'downloads',
    'settings',
    'my-plans',
    'my-downloads'
  ],
  monthly: [
    'plans',
    'downloads',
    'commands',
    'triggers',
    'chatbot',
    'reports',
    'announcements',
    'campaigns',
    'auto-group',
    'auto-private',
    'settings',
    'my-plans',
    'my-downloads'
  ],
  quarterly: [
    'plans',
    'downloads',
    'jarvis',
    'charon',
    'commands',
    'triggers',
    'chatbot',
    'reports',
    'announcements',
    'campaigns',
    'auto-group',
    'auto-private',
    'pix',
    'settings',
    'my-plans',
    'my-downloads'
  ],
  annual: [
    'plans',
    'downloads',
    'instances',
    'jarvis',
    'charon',
    'commands',
    'triggers',
    'chatbot',
    'leads',
    'reports',
    'announcements',
    'campaigns',
    'auto-group',
    'auto-private',
    'pix',
    'settings',
    'my-plans',
    'my-downloads'
  ],
  vitalicio: [
    'plans',
    'downloads',
    'instances',
    'jarvis',
    'charon',
    'commands',
    'triggers',
    'chatbot',
    'leads',
    'reports',
    'announcements',
    'campaigns',
    'auto-group',
    'auto-private',
    'pix',
    'settings',
    'my-plans',
    'my-downloads'
  ],
  master: [
    'plans',
    'downloads',
    'instances',
    'jarvis',
    'charon',
    'commands',
    'triggers',
    'chatbot',
    'leads',
    'reports',
    'announcements',
    'campaigns',
    'auto-group',
    'auto-private',
    'pix',
    'settings',
    'my-plans',
    'my-downloads'
  ],
};

export const planNames: Record<string, string> = {
  free: 'Colaborador',
  monthly: 'Mensal',
  quarterly: 'Trimestral',
  annual: 'Anual',
  vitalicio: 'Vitalício',
  master: 'Master',
};

export const getAvailableFeatures = (plan: string): string[] => {
  return planFeatures[plan] || planFeatures.free;
};
