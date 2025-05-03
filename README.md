# 技術ブログ構成案: FastMCPで構築したMCPサーバーにMastraからアクセスしてみた

## 1. 概要
本記事の目的は、[FastMCP](https://gofastmcp.com/getting-started/welcome)を用いて構築したMCPサーバーに対して、[Mastra](https://mastra.ai/)からアクセスするコードを例を共有することです。

## 2. FastMCPとは
FastMCPはMCPサーバーやMCPクライアントを簡単に実装できるPythonライブラリです。
[公式ドキュメント](https://gofastmcp.com/getting-started/welcome#why-fastmcp%3F)によると、FastMCPは以下のような特徴を持っています。
1. Fast
   - 高レベルインターフェースにより「関数にデコレーターを付けるだけ」で MCP サーバーを公開でき、実装コードと開発期間を最小化します。​
2. Simple
   - 通常は必須となるサーバーセットアップ・プロトコルハンドラ・コンテンツタイプ管理・エラーハンドリングなどの煩雑なコードをフレームワーク側が吸収。開発者はビジネスロジックやツール定義に集中できます。​
3. Pythonic
   - 関数デコレーター @tool @resource @prompt で直感的にエンドポイントを定義でき、純粋な Python コードとして読める点が大きな魅力です。​
4. Complete
   - MCP コア仕様を網羅的にサポートしているため、MCP サーバーを構築する際に必要な機能はすべて揃っています。
  
以下のようにFastMCPのインスタンスを作成し、関数にデコレータを付けるだけでadd関数呼び出せるMCPサーバーを実装できます。

```python
from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    mcp.run()
```

他にできることは公式ドキュメントを参照してみてください。
typescriptでの実装もあるみたいですが、公式ドキュメントが見当たららなかったので一旦今回はPythonで実装しています。
https://github.com/punkpeye/fastmcp

MCPについてはすでにわかりやすい情報が多く存在しているのでそちらを参照してください。
https://speakerdeck.com/minorun365/yasasiimcpru-men
https://zenn.dev/cloud_ace/articles/model-context-protocol

## 3. Mastraとは
[Mastra](https://mastra.ai/)はAgentやWorkflowを簡単に構築できるTypescriptのフレームワークです。
RAGの構築やLLMOpsに必要なTracingやEvaluationなども充実しており、Agentの実装をアプリケーションに組み込む際の選択肢に入ってきそうな雰囲気を感じています。
筆者の所属する会社でも、これまではLangGraphを用いてAgentの開発を行っていたのですが、MastraやAI SDKでの開発体験が非常に良いので今後はMastraを用いてAgentの開発を行っていこうかなとゆるく考えてます。

MastraはMCPにAll-Inする旨の記事を出しているため、MCP周りの実装も簡単です。
https://mastra.ai/blog/mastra-mcp

Mastraについては日本語の記事が多く存在していますが、機能追加が高速に行われているため、常に公式のドキュメントも参照することをお勧めします。

## 3. MastraのチュートリアルのでAgentが使うToolをFastMCPでMCPサーバー化する
それでは本記事の本題であるFastMCPでMCPサーバーを実装し、Mastraからアクセスする手順を説明します。
今回はMastraを初期化した際に実装されているWetherAgentで使うツールをFastMCPで実装します。

``` typescript
import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { weatherTool } from '../tools';

export const weatherAgent = new Agent({
  name: 'Weather Agent',
  instructions: `
      You are a helpful weather assistant that provides accurate weather information.

      Your primary function is to help users get weather details for specific locations. When responding:
      - Always ask for a location if none is provided
      - If the location name isn’t in English, please translate it
      - If giving a location with multiple parts (e.g. "New York, NY"), use the most relevant part (e.g. "New York")
      - Include relevant details like humidity, wind conditions, and precipitation
      - Keep responses concise but informative

      Use the weatherTool to fetch current weather data.
`,
  model: openai('gpt-4o'),
  tools: { weatherTool },
  memory: new Memory({
    options: {
      lastMessages: 10,
      semanticRecall: false,
      threads: {
        generateTitle: false,
      },
    },
  }),
});
```

## 3.1 Mastraの初期化
1. まずはMastraのプロジェクトを作成します。インストール時に色々聞かれますが今回はrecommendedを選択しておけば大丈夫です。
  ```bash
  npx create-mastra@latest 
  ```
2. Mastraサーバーを起動。
  ```bash
  npm run dev
  ```
3. localhost:4111にアクセスして、MastraのダッシュボードにアクセスしてWeatherAgentを選択し、適当に話しかけてレスポンスが帰って来れば問題ないです。
   ![alt text](image-2.png)

この段階ではWeatherAgentはmastra/tools配下に実装されているweatherToolを用いて天気情報を取得しています。
次はこれをFastMCPでMCPサーバー化します。

## 3.1 FastMCPでの実装
まずはpythonプロジェクトを作成し、FastMCPをインストールします。
```bash
uv init --lib weather_tools
uv add fastmcp
```

FastMCPとはのセクションで記載した通り、FastMCPは関数にデコレータを付けるだけでMCPサーバーを実装できます。
MastraのweatherToolの実装をpythonに移植していきます。今回は実装の詳細というよりかは、MCPサーバー化することにフォーカスしているので、Gemini 2.5Proで全て移植しました。
コードの詳細はGithubに載せているので、そちらを参照してください。

```python
import httpx
from pydantic import BaseModel, Field
from typing import List, Optional
from fastmcp import FastMCP

mcp = FastMCP("MCP Servers to get weather data")

...省略

@mcp.tool()
async def get_weather(location: str) -> WeatherOutput:
    """Gets the current weather for a given location using Open-Meteo APIs."""
    async with httpx.AsyncClient() as client:
        # 1. Geocoding: Get coordinates for the location
        geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
        try:
            geo_response = await client.get(geocoding_url)
            geo_response.raise_for_status() # Raise an exception for bad status codes
            geocoding_data = GeocodingResponse.model_validate(geo_response.json())
        except httpx.HTTPStatusError as e:
            raise Exception(f"Geocoding API request failed: {e.response.status_code}") from e
        except Exception as e:
            raise Exception(f"Failed to parse geocoding response: {e}") from e


        if not geocoding_data.results:
            raise ValueError(f"Location '{location}' not found")

        geo_result = geocoding_data.results[0]
        latitude = geo_result.latitude
        longitude = geo_result.longitude
        found_location_name = geo_result.name

        # 2. Weather Forecast: Get weather for the coordinates
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
            f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,weather_code"
        )
        try:
            weather_response = await client.get(weather_url)
            weather_response.raise_for_status()
            weather_data = WeatherResponse.model_validate(weather_response.json())
        except httpx.HTTPStatusError as e:
             raise Exception(f"Weather API request failed: {e.response.status_code}") from e
        except Exception as e:
            raise Exception(f"Failed to parse weather response: {e}") from e


        current_weather = weather_data.current

        # 3. Format Output
        output = WeatherOutput(
            temperature=current_weather.temperature_2m,
            feelsLike=current_weather.apparent_temperature,
            humidity=current_weather.relative_humidity_2m,
            windSpeed=current_weather.wind_speed_10m,
            windGust=current_weather.wind_gusts_10m,
            conditions=get_weather_condition(current_weather.weather_code),
            location=found_location_name,
        )
        return output

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

## 3.2 MastraからFastMCPのMCPサーバーにアクセス
次にMastraからFastMCPのMCPサーバーにアクセスするためにAgentのコードを修正します。
まず、修正後のAgentの実装全体を示してから、修正点を説明します。

```typescript
import { openai } from '@ai-sdk/openai';
import { Agent } from '@mastra/core/agent';
import { Memory } from '@mastra/memory';
import { MCPClient } from '@mastra/mcp';

const mcp = new MCPClient({
  servers: {
    weather: {
      "command": "uv",
      "args": [
        "--directory",
        "absolute_path_to_your_mcp_server",
        "run",
        "main.py"
      ]
    },
  },
});

export const weatherAgent = new Agent({
  name: 'Weather Agent',
  instructions: `
      You are a helpful weather assistant that provides accurate weather information.

      Your primary function is to help users get weather details for specific locations. When responding:
      - Always ask for a location if none is provided
      - If the location name isn’t in English, please translate it
      - If giving a location with multiple parts (e.g. "New York, NY"), use the most relevant part (e.g. "New York")
      - Include relevant details like humidity, wind conditions, and precipitation
      - Keep responses concise but informative

      Use the weatherTool to fetch current weather data.
`,
  model: openai('gpt-4.1-nano'),
  memory: new Memory({
    options: {
      lastMessages: 10,
      semanticRecall: false,
      threads: {
        generateTitle: false,
      },
    },
  }),
  tools: await mcp.getTools(),
});
```

1つ目の修正点は、MCPClientを使ってMastraからMCPサーバーにアクセスするための設定を行います。
```typescript
const mcp = new MCPClient({
  servers: {
    weather: {
      "command": "uv",
      "args": [
        "--directory",
        "absolute_path_to_your_mcp_server",
        "run",
        "main.py"
      ]
    },
  },
});
```
absolute_path_to_your_mcp_serverはFastMCPのMCPサーバーを実行しているディレクトリの絶対パスに置き換えてください。

2つ目の修正点は、Agentの初期化時にweatherToolではなく、MCPClientを用いて取得したツールを指定します。
以下のようにするだけで簡単にMCPで利用できるツールを取得できます。
```typescript
  tools: await mcp.getTools(),
```

あとは再度Mastraサーバーを起動して、ダッシュボードからWeatherAgentを選択し、東京の天気を聞いてみます。

MCPサーバーに実装したget_weather関数が呼び出され、正しく回答されていることがわかります。


toolに対するリクエスト
```json
{
  "location": "Tokyo"
}
```

ツール(MCPサーバー)からのレスポンス
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"temperature\": 17.0, \"feelsLike\": 17.2, \"humidity\": 76, \"windSpeed\": 5.0, \"windGust\": 33.8, \"conditions\": \"Clear sky\", \"location\": \"Tokyo\"}"
    }
  ],
  "isError": false
}
```
