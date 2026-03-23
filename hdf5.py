import h5py

# Abre el archivo HDF5 en modo lectura
f = h5py.File('E:\Catalogo\Gaia DR3\VariClassifierDefinition_001.hdf5', 'r')

# Imprime el contenido del archivo
print("Keys: %s" % f.keys())
a_group_key = list(f.keys())[0]

# Toma los datos de un grupo
data = list(f[a_group_key])
print(data)

# Cierra el archivo
f.close()
