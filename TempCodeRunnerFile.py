def delete_unit_by_number(self, unit_number):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT status
            FROM units
            WHERE unit_number = ?
        """, (unit_number,))

        unit = cursor.fetchone()

        if unit is None:
            return False, "Unit not found."

        if unit["status"] == "Occupied":
            return False, "Occupied units cannot be deleted."

        cursor.execute("""
            DELETE FROM units
            WHERE unit_number = ?
        """, (unit_number,))

        self.connection.commit()

        return True, "Unit deleted successfully."
