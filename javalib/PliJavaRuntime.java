import java.io.*;
import java.sql.*;
import java.util.*;
import java.net.*;
import java.util.logging.Logger;

/**
 * plijava runtime helper - database access and credential parsing.
 * Generated Java programs call PliJavaRuntime.executeQuery() and
 * PliJavaRuntime.parseCredentials() instead of embedding these methods inline.
 */
public class PliJavaRuntime {

    /**
     * Executes a SELECT SQL query and returns the first column of the first row.
     * Supports MySQL and Db2 LUW via dynamic JDBC driver loading.
     */
    public static String executeQuery(
            String dbsys,
            String jdbc_path,
            String port,
            String sql_statement,
            String host,
            String dbName,
            String user,
            String password)
            throws
            MalformedURLException,
            ClassNotFoundException,
            InstantiationException,
            IllegalAccessException {

        Connection connection = null;
        Statement statement = null;
        String result = "";
        String classname;
        URL u;
        StringBuilder url;

        System.out.println("=========== database call parameters =========");
        System.out.println("dbsys:"      + dbsys);
        System.out.println("jdbc_path:"  + jdbc_path);
        System.out.println("port:"       + port);
        System.out.println("host:"       + host);
        System.out.println("dbname:"     + dbName);
        System.out.println("user:"       + user);
        System.out.println("password:"   + password);
        System.out.println("=========== database call results ============");

        switch (dbsys) {
            case "db2":
                classname = "com.ibm.db2.jcc.DB2Driver";
                url = new StringBuilder("jdbc:db2://");
                break;
            case "mysql":
                classname = "com.mysql.cj.jdbc.Driver";
                url = new StringBuilder("jdbc:mysql://");
                break;
            default:
                return "E:No database system (db2, mysql) selected";
        }

        u = new URL("jar:file:" + jdbc_path + "!/");
        try {
            URLClassLoader ucl = new URLClassLoader(new URL[]{u});
            Driver d = (Driver) Class.forName(classname, true, ucl).newInstance();
            DriverManager.registerDriver(new DriverShim(d));
            String portv = ":" + port + "/";
            url.append(host).append(portv).append(dbName);
            System.out.println("URL: " + url.toString());
            connection = DriverManager.getConnection(url.toString(), user, password);
            statement  = connection.createStatement();
            ResultSet resultSet = statement.executeQuery(sql_statement);
            if (resultSet.next()) {
                result = resultSet.getString(1);
            }
        } catch (SQLException e) {
            System.out.println("E:SQL Error");
            e.printStackTrace();
            return "E:Error connecting to database";
        } finally {
            try {
                if (statement  != null) statement.close();
                if (connection != null) connection.close();
            } catch (SQLException e) {
                e.printStackTrace();
            }
        }
        return result;
    }

    /**
     * Parses a key=value credential file (lines starting with # are comments).
     * Expected keys: dbsys, jdbc_path, port, host, user, password, database.
     */
    public static Map<String, String> parseCredentials(String filePath) throws IOException {
        List<String> lines = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new FileReader(filePath))) {
            String line;
            System.out.println("path=" + filePath);
            while ((line = reader.readLine()) != null) {
                if (!line.substring(0, 1).equals("#")) {
                    lines.add(line.trim());
                }
            }
        }
        StringBuilder contentBuilder = new StringBuilder();
        for (String line : lines) {
            contentBuilder.append(line);
        }
        String content = contentBuilder.toString();
        Map<String, String> params = new HashMap<>();
        String[] pairs = content.split(", ");
        for (String pair : pairs) {
            String[] keyValue = pair.split("=");
            String key   = keyValue[0].trim();
            String value = keyValue[1].trim().replaceAll("[\']", "");
            params.put(key, value);
        }
        return params;
    }
}
