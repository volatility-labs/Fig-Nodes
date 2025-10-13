# Get a generation

GET https://openrouter.ai/api/v1/generation

Returns metadata about a specific generation request

## OpenAPI Specification

```yaml
openapi: 3.1.1
info:
  title: Get a generation
  version: endpoint_.getAGeneration
paths:
  /generation:
    get:
      operationId: get-a-generation
      summary: Get a generation
      description: Returns metadata about a specific generation request
      tags:
        - []
      parameters:
        - name: id
          in: query
          required: true
          schema:
            type: string
        - name: Authorization
          in: header
          description: >-
            Bearer authentication of the form `Bearer <token>`, where token is
            your auth token.
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Returns the request metadata for this generation
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/getAGeneration_Response_200'
components:
  schemas:
    GenerationGetResponsesContentApplicationJsonSchemaData:
      type: object
      properties:
        id:
          type: string
        upstream_id:
          type:
            - string
            - 'null'
        total_cost:
          type: number
          format: double
        cache_discount:
          type:
            - number
            - 'null'
          format: double
        upstream_inference_cost:
          type:
            - number
            - 'null'
          format: double
        created_at:
          type: string
        model:
          type: string
        app_id:
          type:
            - integer
            - 'null'
        streamed:
          type:
            - boolean
            - 'null'
        cancelled:
          type:
            - boolean
            - 'null'
        provider_name:
          type:
            - string
            - 'null'
        latency:
          type:
            - integer
            - 'null'
        moderation_latency:
          type:
            - integer
            - 'null'
        generation_time:
          type:
            - integer
            - 'null'
        finish_reason:
          type:
            - string
            - 'null'
        native_finish_reason:
          type:
            - string
            - 'null'
        tokens_prompt:
          type:
            - integer
            - 'null'
        tokens_completion:
          type:
            - integer
            - 'null'
        native_tokens_prompt:
          type:
            - integer
            - 'null'
        native_tokens_completion:
          type:
            - integer
            - 'null'
        native_tokens_reasoning:
          type:
            - integer
            - 'null'
        num_media_prompt:
          type:
            - integer
            - 'null'
        num_media_completion:
          type:
            - integer
            - 'null'
        num_search_results:
          type:
            - integer
            - 'null'
        origin:
          type: string
        usage:
          type: number
          format: double
        is_byok:
          type: boolean
      required:
        - id
        - total_cost
        - created_at
        - model
        - origin
        - usage
        - is_byok
    getAGeneration_Response_200:
      type: object
      properties:
        data:
          $ref: >-
            #/components/schemas/GenerationGetResponsesContentApplicationJsonSchemaData
      required:
        - data

```

## SDK Code Examples

```python
import requests

url = "https://openrouter.ai/api/v1/generation"

querystring = {"id":"id"}

headers = {"Authorization": "Bearer <token>"}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())
```

```javascript
const url = 'https://openrouter.ai/api/v1/generation?id=id';
const options = {method: 'GET', headers: {Authorization: 'Bearer <token>'}};

try {
  const response = await fetch(url, options);
  const data = await response.json();
  console.log(data);
} catch (error) {
  console.error(error);
}
```

```go
package main

import (
	"fmt"
	"net/http"
	"io"
)

func main() {

	url := "https://openrouter.ai/api/v1/generation?id=id"

	req, _ := http.NewRequest("GET", url, nil)

	req.Header.Add("Authorization", "Bearer <token>")

	res, _ := http.DefaultClient.Do(req)

	defer res.Body.Close()
	body, _ := io.ReadAll(res.Body)

	fmt.Println(res)
	fmt.Println(string(body))

}
```

```ruby
require 'uri'
require 'net/http'

url = URI("https://openrouter.ai/api/v1/generation?id=id")

http = Net::HTTP.new(url.host, url.port)
http.use_ssl = true

request = Net::HTTP::Get.new(url)
request["Authorization"] = 'Bearer <token>'

response = http.request(request)
puts response.read_body
```

```java
HttpResponse<String> response = Unirest.get("https://openrouter.ai/api/v1/generation?id=id")
  .header("Authorization", "Bearer <token>")
  .asString();
```

```php
<?php

$client = new \GuzzleHttp\Client();

$response = $client->request('GET', 'https://openrouter.ai/api/v1/generation?id=id', [
  'headers' => [
    'Authorization' => 'Bearer <token>',
  ],
]);

echo $response->getBody();
```

```csharp
var client = new RestClient("https://openrouter.ai/api/v1/generation?id=id");
var request = new RestRequest(Method.GET);
request.AddHeader("Authorization", "Bearer <token>");
IRestResponse response = client.Execute(request);
```

```swift
import Foundation

let headers = ["Authorization": "Bearer <token>"]

let request = NSMutableURLRequest(url: NSURL(string: "https://openrouter.ai/api/v1/generation?id=id")! as URL,
                                        cachePolicy: .useProtocolCachePolicy,
                                    timeoutInterval: 10.0)
request.httpMethod = "GET"
request.allHTTPHeaderFields = headers

let session = URLSession.shared
let dataTask = session.dataTask(with: request as URLRequest, completionHandler: { (data, response, error) -> Void in
  if (error != nil) {
    print(error as Any)
  } else {
    let httpResponse = response as? HTTPURLResponse
    print(httpResponse)
  }
})

dataTask.resume()
```