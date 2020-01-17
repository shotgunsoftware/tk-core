# Github API Fixtures

To test the Github API, we use some test data collected by making calls to the real Github API and storing the results here.  To update or generate these files, you can use curl as follows:

`curl -D somefile.header -o somefile.json https://api.github.com/some/api/path`
Where `somefile` is the `page_name` you intend to use with the `MockResponse` object, and the url you retrieve is for the API call you intend to mock.
