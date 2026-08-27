### Parallelize independent fetches

When a request chain is caused by two or more fetches that do not depend on each other, start them together instead of waiting for one to finish before kicking off the next. This can reduce the total waiting time when the data is consumed together and there is no dependency between the calls.

**Good example:**
```typescript
const citiesPromise = apiClient.createCitiesEndpoint(baseUrl).load();
const cityPromise = apiClient.createCityEndpoint(baseUrl).load({ city: cityCode });

const [cities, city] = await Promise.all([citiesPromise, cityPromise]);

setCities(cities);
setCity(city);
```

Use this when the data is consumed together and there is no dependency between the calls.