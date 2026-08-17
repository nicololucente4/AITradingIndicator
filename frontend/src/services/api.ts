const API_BASE_URL = "http://127.0.0.1:8000";

export async function getHealth() {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/health`,
    {
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error("Health endpoint not available");
  }

  return response.json();
}

export async function getSystemStatus() {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/system/status`,
    {
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error("System status endpoint not available");
  }

  return response.json();
}

export async function getCandles(
  limit = 500
) {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/market/candles?limit=${limit}`,
    {
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      "Candles endpoint not available"
    );
  }

  return response.json();
}