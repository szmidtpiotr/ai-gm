window.API_HEALTH = '/api/health';
window.API_MODELS = '/api/models';
window.API_CAMPAIGNS = '/api/campaigns';

/**
 * GET /api/campaigns/:id — pass viewer `user_id` so owner/admin/gm can receive `gm_plan_json` (T07).
 * @param {string|number} campaignId
 * @returns {string}
 */
window.apiCampaignGetUrl = function (campaignId) {
  const id = String(campaignId ?? '').trim();
  if (!id) {
    return '/api/campaigns/';
  }
  const uid = window.state?.playerUserId;
  if (uid == null || uid === '') {
    return `/api/campaigns/${id}`;
  }
  return `/api/campaigns/${id}?user_id=${encodeURIComponent(String(uid))}`;
};