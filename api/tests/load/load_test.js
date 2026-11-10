import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// Load deterministic test users provisioned by setup_load_data.py
const users = JSON.parse(open('./load_users.json'));

// Custom Trend metrics per endpoint to verify NFR-001 and NFR-003
const dashboardDuration = new Trend('dashboard_duration', true);
const inventoryDuration = new Trend('inventory_duration', true);
const recommendationsDuration = new Trend('recommendations_duration', true);
const recipeDetailDuration = new Trend('recipe_detail_duration', true);
const healthDuration = new Trend('health_duration', true);
const rateLimitCount = new Counter('rate_limit_responses');
const successRate = new Rate('success_rate');

export const options = {
  scenarios: {
    steady_100_users: {
      executor: 'ramping-vus',
      startVUs: 10,
      stages: [
        { duration: '10s', target: 50 },    // Ramp up to 50 users
        { duration: '10s', target: 100 },   // Ramp up to 100 concurrent users
        { duration: '30s', target: 100 },   // Steady state: 100 concurrent users
        { duration: '10s', target: 0 },     // Ramp down
      ],
      gracefulRampDown: '5s',
    },
  },
  thresholds: {
    // PRD NFR-001: P95 latency for non-AI endpoints under 300 ms at 100 concurrent users
    http_req_duration: ['p(95)<300'],
    // PRD NFR-003: Recipe recommendation returns within 2 seconds P95 when cached
    recommendations_duration: ['p(95)<2000'],
    // Error rate must remain under 1%
    http_req_failed: ['rate<0.01'],
    success_rate: ['rate>0.99'],
  },
};

const BASE_URL = __ENV.API_HOST || 'http://127.0.0.1:8000';

export default function () {
  // Map VU to isolated deterministic user (modulo for safe wrapping)
  const userIndex = (__VU - 1) % users.length;
  const user = users[userIndex];

  const authHeaders = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${user.token}`,
  };

  // 1. Dashboard summary (PRD Section 6.8 & 11.10)
  {
    const res = http.get(`${BASE_URL}/api/v1/dashboard`, { headers: authHeaders, tags: { name: 'Dashboard' } });
    dashboardDuration.add(res.timings.duration);
    const ok = check(res, {
      'dashboard status 200': (r) => r.status === 200,
      'dashboard has freshness': (r) => r.body && r.body.includes('status_counts'),
    });
    successRate.add(ok);
    if (res.status === 429) rateLimitCount.add(1);
  }

  // Realistic user pacing between page transitions (0.8s per PRD mobile navigation)
  sleep(0.8);

  // 2. Kitchen Inventory list (PRD Section 6.3 & 11.3)
  {
    const res = http.get(`${BASE_URL}/api/v1/inventory`, { headers: authHeaders, tags: { name: 'Inventory' } });
    inventoryDuration.add(res.timings.duration);
    const ok = check(res, {
      'inventory status 200': (r) => r.status === 200,
      'inventory returns items': (r) => r.body && r.body.includes('items'),
    });
    successRate.add(ok);
    if (res.status === 429) rateLimitCount.add(1);
  }

  sleep(0.8);

  // 3. Recipe Recommendations - Cached Fast Path (PRD Section 6.5, 7.1, 11.6, 14.7)
  {
    const res = http.get(`${BASE_URL}/api/v1/recommendations?limit=5&servings=2`, {
      headers: authHeaders,
      tags: { name: 'RecommendationsCached' },
    });
    recommendationsDuration.add(res.timings.duration);
    const ok = check(res, {
      'recommendations status 200': (r) => r.status === 200,
      'recommendations has items': (r) => r.body && r.body.includes('items'),
    });
    successRate.add(ok);
    if (res.status === 429) rateLimitCount.add(1);
  }

  sleep(0.8);

  // 4. Recipe Detail & Dynamic Servings (PRD Section 6.5 & 11.6)
  {
    const res = http.get(`${BASE_URL}/api/v1/recipes/aloo_gobi?servings=2`, {
      headers: authHeaders,
      tags: { name: 'RecipeDetail' },
    });
    recipeDetailDuration.add(res.timings.duration);
    const ok = check(res, {
      'recipe detail status 200': (r) => r.status === 200,
      'recipe detail title valid': (r) => r.body && r.body.includes('Aloo Gobi'),
    });
    successRate.add(ok);
    if (res.status === 429) rateLimitCount.add(1);
  }

  sleep(0.8);

  // 5. Health Check endpoint (PRD Section 11.11)
  {
    const res = http.get(`${BASE_URL}/api/health`, { tags: { name: 'Health' } });
    healthDuration.add(res.timings.duration);
    const ok = check(res, {
      'health status 200': (r) => r.status === 200,
    });
    successRate.add(ok);
  }

  // Realistic user pacing between full task iterations (0.5s - 1.5s)
  sleep(0.5 + Math.random());
}

