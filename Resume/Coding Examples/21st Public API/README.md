This is the API for the 21st app.

The API provides four main functions:
  1. Allows users to suggest notifications:
    These notifications are stored in our SQL database.
    A text is also sent out to app Admins with the suggested notification

  2. Allows Admins to post notifications to all devices:
    Admins, with the proper keys, can post notifications publicly to all devices.
    This updates the SQL database with a new public notification and
    sends an IOS push notification to all subscribed devices

  3. Allows devices to update their tables of recent notifications:
    A get request can be made that will return a set of recently posted
    public notifications in chronological order

  4. Allows notifications to be deleted:
    private and public notifications can be deletes through endpoints by Admins
    with the correct keys.
    
