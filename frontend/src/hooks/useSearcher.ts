import { useRef, useState } from "react";

export type SearchOption = { value: string; label: string };

export function useSearcher(
  searchFn: (query: string) => Promise<SearchOption[]>,
  debounceMs = 200,
) {
  const [options, setOptions] = useState<SearchOption[]>([]);
  const [fetching, setFetching] = useState(false);
  const timer = useRef<number>();
  const sequence = useRef(0);

  function onSearch(query: string) {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      const requestId = ++sequence.current;
      setFetching(true);
      try {
        const nextOptions = await searchFn(query);
        if (requestId === sequence.current) setOptions(nextOptions);
      } catch {
        if (requestId === sequence.current) setOptions([]);
      } finally {
        if (requestId === sequence.current) setFetching(false);
      }
    }, debounceMs);
  }

  return { options, fetching, onSearch, setOptions };
}
